"""
Portfolio Backtester - Combine multiple strategies with regime-aware allocation.

Usage:
  python tools/portfolio_backtest.py <data-file> [--regime]

Runs each strategy independently, then combines equity curves using either:
  - Fixed allocation weights (default: equal weight)
  - Regime-based dynamic allocation (--regime flag)

Reports:
  - Individual strategy performance
  - Combined portfolio performance
  - Correlation between strategy returns
  - Drawdown overlap analysis (do they lose at the same time?)
"""

import sys
import os
import json
import subprocess
import tempfile
import argparse
import numpy as np
import pandas as pd
from datetime import datetime

# Strategy configs to include in portfolio
STRATEGIES = {
    'mean_rev': {
        'config': 'config/strategies/production/mean_rev_quiet_filter.yaml',
        'label': 'Mean Reversion (V2)',
        'weight': 0.5,
    },
    'trend_follow': {
        'config': 'config/strategies/development/tf_test_wide_breakout.yaml',
        'label': 'Trend Following (40-bar)',
        'weight': 0.5,
    },
}

# Regime classification thresholds (calibrated from ES data)
REGIME_CONFIG = {
    'atr_period': 14,
    'adx_period': 14,
    'lookback': 20,         # bars for regime classification
    'trending_adx': 25,     # ADX above this = trending regime
    'high_vol_atr_pct': 75, # ATR above this percentile = high vol
    # Allocation weights per regime: {regime: {strategy_key: weight}}
    'allocations': {
        'trending_highvol': {'mean_rev': 0.2, 'trend_follow': 0.8},
        'trending_lowvol':  {'mean_rev': 0.3, 'trend_follow': 0.7},
        'ranging_highvol':  {'mean_rev': 0.5, 'trend_follow': 0.5},
        'ranging_lowvol':   {'mean_rev': 0.8, 'trend_follow': 0.2},
    },
}


def run_backtest(config_path, data_file):
    """Run a single strategy backtest, return the JSON results path."""
    cmd = [
        sys.executable, 'src/backtest/run_backtest.py',
        '--config', config_path,
        '--data-file', data_file,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print(f"  [FAIL] Backtest failed for {config_path}")
        print(f"  stderr: {result.stderr[-200:] if result.stderr else 'none'}")
        return None, None, None

    # Extract results file paths from output
    json_path = None
    trades_path = None
    equity_path = None
    for line in result.stdout.split('\n'):
        if 'Full results saved to:' in line:
            json_path = line.split(':', 1)[1].strip()
        elif 'Trades saved to:' in line:
            trades_path = line.split(':', 1)[1].strip()
        elif 'Equity curve saved to:' in line:
            equity_path = line.split(':', 1)[1].strip()

    return json_path, trades_path, equity_path


def load_metrics(json_path):
    """Load backtest metrics from JSON results file."""
    if not json_path or not os.path.exists(json_path):
        return {}
    with open(json_path, 'r') as f:
        return json.load(f)


def load_equity_curve(equity_path):
    """Load equity curve as pandas Series."""
    if not equity_path or not os.path.exists(equity_path):
        return None
    df = pd.read_csv(equity_path, index_col=0, parse_dates=True)
    # Ensure timezone-naive datetime index for compatibility with regime data
    df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
    if 'equity' in df.columns:
        return df['equity']
    return df.iloc[:, 0]


def load_trades(trades_path):
    """Load trades as DataFrame."""
    if not trades_path or not os.path.exists(trades_path):
        return None
    return pd.read_csv(trades_path, parse_dates=['entry_time', 'exit_time'])


def classify_regime(data, config):
    """Classify each bar into a regime based on ATR and ADX levels.

    Returns a DataFrame with columns: atr, adx, regime
    """
    df = data.copy()

    # ATR
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift(1)).abs()
    lc = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=config['atr_period']).mean()

    # ADX
    up = df['high'] - df['high'].shift()
    down = df['low'].shift() - df['low']
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    atr_smooth = tr.rolling(window=config['adx_period']).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(config['adx_period']).mean() / atr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(config['adx_period']).mean() / atr_smooth)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.rolling(window=config['adx_period']).mean()

    # Rolling ATR percentile for vol classification
    df['atr_pct'] = df['atr'].rolling(window=252*12).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False
    )
    # Fill early bars with simple percentile
    df['atr_pct'] = df['atr_pct'].fillna(50)

    # Classify
    trending = df['adx'] >= config['trending_adx']
    high_vol = df['atr_pct'] >= config['high_vol_atr_pct']

    df['regime'] = 'ranging_lowvol'
    df.loc[trending & high_vol, 'regime'] = 'trending_highvol'
    df.loc[trending & ~high_vol, 'regime'] = 'trending_lowvol'
    df.loc[~trending & high_vol, 'regime'] = 'ranging_highvol'

    return df[['atr', 'adx', 'atr_pct', 'regime']]


def compute_portfolio_equity(equity_curves, weights, data=None, regime_config=None):
    """Combine equity curves with allocation weights.

    If data and regime_config are provided, uses dynamic regime-based allocation.
    Otherwise uses fixed weights.

    Returns: combined equity Series, daily returns correlation
    """
    # Align all equity curves to the same index
    aligned = pd.DataFrame()
    for key, eq in equity_curves.items():
        if eq is not None:
            aligned[key] = eq
    aligned = aligned.ffill().bfill()

    # Calculate returns for each strategy
    returns = aligned.pct_change().fillna(0)

    if data is not None and regime_config is not None:
        # Dynamic regime-based allocation
        regimes = classify_regime(data, regime_config)
        # Align regime to equity curve index
        regimes = regimes.reindex(aligned.index, method='ffill')

        alloc_df = pd.DataFrame(0.0, index=aligned.index,
                                columns=list(equity_curves.keys()))
        allocations = regime_config['allocations']
        for regime_name, strat_weights in allocations.items():
            mask = regimes['regime'] == regime_name
            for strat_key, w in strat_weights.items():
                if strat_key in alloc_df.columns:
                    alloc_df.loc[mask, strat_key] = w

        # Normalize weights (in case not all strategies are present)
        row_sums = alloc_df.sum(axis=1).replace(0, 1)
        alloc_df = alloc_df.div(row_sums, axis=0)

        # Weighted returns
        weighted_returns = (returns * alloc_df).sum(axis=1)
        label = 'regime-weighted'
    else:
        # Fixed weights
        total_weight = sum(weights.get(k, 0) for k in aligned.columns)
        norm_weights = {k: weights.get(k, 0) / total_weight for k in aligned.columns}
        weighted_returns = sum(returns[k] * w for k, w in norm_weights.items())
        label = 'fixed-weight'

    # Build combined equity curve
    initial = 10000
    combined = (1 + weighted_returns).cumprod() * initial

    # Correlation of daily returns
    corr = returns.corr() if len(returns.columns) > 1 else pd.DataFrame()

    return combined, corr, label


def compute_metrics(equity_series, label=''):
    """Compute standard performance metrics from an equity curve."""
    if equity_series is None or len(equity_series) < 2:
        return {}

    returns = equity_series.pct_change().dropna()
    total_return = (equity_series.iloc[-1] / equity_series.iloc[0] - 1) * 100

    # Max drawdown
    peak = equity_series.cummax()
    dd = (equity_series - peak) / peak * 100
    max_dd = dd.min()

    # Sharpe (annualized, assuming 5-min bars ~78 bars/day, 252 days)
    if returns.std() > 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(78 * 252)
    else:
        sharpe = 0

    return {
        'label': label,
        'total_return_pct': round(total_return, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'sharpe': round(sharpe, 2),
        'final_equity': round(equity_series.iloc[-1], 2),
    }


def print_results(individual_metrics, portfolio_metrics, correlation, regime_counts=None):
    """Print formatted comparison table."""
    print("\n" + "=" * 70)
    print("PORTFOLIO BACKTEST RESULTS")
    print("=" * 70)

    print("\nIndividual Strategy Performance:")
    print(f"{'Strategy':<30} {'Return':>8} {'MaxDD':>8} {'Sharpe':>8} {'Final $':>10}")
    print("-" * 70)
    for key, m in individual_metrics.items():
        label = STRATEGIES.get(key, {}).get('label', key)
        print(f"{label:<30} {m.get('total_return_pct', 0):>7.2f}% {m.get('max_drawdown_pct', 0):>7.2f}% "
              f"{m.get('sharpe', 0):>8.2f} ${m.get('final_equity', 0):>9.2f}")

    print(f"\n{'COMBINED PORTFOLIO':<30} {portfolio_metrics.get('total_return_pct', 0):>7.2f}% "
          f"{portfolio_metrics.get('max_drawdown_pct', 0):>7.2f}% "
          f"{portfolio_metrics.get('sharpe', 0):>8.2f} ${portfolio_metrics.get('final_equity', 0):>9.2f}")

    if not correlation.empty:
        print("\nReturn Correlation Matrix:")
        for col in correlation.columns:
            label = STRATEGIES.get(col, {}).get('label', col)[:20]
            vals = '  '.join(f"{correlation.loc[col, c]:>6.3f}" for c in correlation.columns)
            print(f"  {label:<20} {vals}")

    if regime_counts is not None:
        print("\nRegime Distribution:")
        total = regime_counts.sum()
        for regime, count in regime_counts.items():
            pct = count / total * 100
            alloc = REGIME_CONFIG['allocations'].get(regime, {})
            alloc_str = ', '.join(f"{k}={v:.0%}" for k, v in alloc.items())
            print(f"  {regime:<22} {pct:5.1f}% of bars  -> {alloc_str}")

    # Key insight: diversification benefit
    individual_dds = [m.get('max_drawdown_pct', 0) for m in individual_metrics.values()]
    worst_individual_dd = min(individual_dds)
    portfolio_dd = portfolio_metrics.get('max_drawdown_pct', 0)
    if worst_individual_dd < 0:
        dd_reduction = ((portfolio_dd - worst_individual_dd) / abs(worst_individual_dd)) * 100
        print(f"\nDiversification Benefit:")
        print(f"  Worst individual MaxDD: {worst_individual_dd:.2f}%")
        print(f"  Portfolio MaxDD:        {portfolio_dd:.2f}%")
        print(f"  Drawdown reduction:     {dd_reduction:.1f}%")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Portfolio Backtest')
    parser.add_argument('data_file', help='Data file in data/historical/')
    parser.add_argument('--regime', action='store_true',
                        help='Use regime-based dynamic allocation')
    args = parser.parse_args()

    print("=" * 70)
    print("PORTFOLIO BACKTESTER")
    print("=" * 70)
    print(f"\nData: {args.data_file}")
    print(f"Mode: {'Regime-weighted' if args.regime else 'Fixed equal-weight'}")
    print(f"Strategies: {len(STRATEGIES)}")
    for key, s in STRATEGIES.items():
        print(f"  {key}: {s['label']} (weight={s['weight']})")

    # Run individual backtests
    print("\n--- Running individual backtests ---")
    equity_curves = {}
    individual_metrics = {}
    weights = {}

    for key, strat in STRATEGIES.items():
        print(f"\nRunning: {strat['label']}...")
        json_path, trades_path, equity_path = run_backtest(strat['config'], args.data_file)

        metrics = load_metrics(json_path)
        equity = load_equity_curve(equity_path)

        if equity is not None:
            equity_curves[key] = equity
            individual_metrics[key] = compute_metrics(equity, strat['label'])
            weights[key] = strat['weight']
            trades = load_trades(trades_path)
            n_trades = len(trades) if trades is not None else 0
            print(f"  -> {individual_metrics[key].get('total_return_pct', 0):.2f}%, "
                  f"{n_trades} trades")
        else:
            print(f"  -> No equity curve generated")

    if len(equity_curves) < 2:
        print("\nERROR: Need at least 2 strategy equity curves for portfolio analysis.")
        return

    # Load data for regime classification if needed
    data = None
    regime_counts = None
    if args.regime:
        data_path = os.path.join('data/historical', args.data_file)
        data = pd.read_csv(data_path, index_col=0, parse_dates=True)
        data.index = pd.to_datetime(data.index, utc=True).tz_localize(None)
        regimes = classify_regime(data, REGIME_CONFIG)
        regime_counts = regimes['regime'].value_counts()

    # Combine equity curves
    print("\n--- Computing portfolio performance ---")
    combined_equity, correlation, label = compute_portfolio_equity(
        equity_curves, weights,
        data=data if args.regime else None,
        regime_config=REGIME_CONFIG if args.regime else None,
    )
    portfolio_metrics = compute_metrics(combined_equity, f'Portfolio ({label})')

    # Print results
    print_results(individual_metrics, portfolio_metrics, correlation, regime_counts)

    # Save combined equity curve
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = f'logs/portfolio_{timestamp}.csv'
    combined_equity.to_csv(out_path, header=['equity'])
    print(f"\nPortfolio equity saved to: {out_path}")


if __name__ == '__main__':
    main()
