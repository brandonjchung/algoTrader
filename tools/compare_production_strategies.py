"""
Production Strategy Comparison
==============================
Tests all production-ready strategies on the same dataset for comparison.

Strategies tested:
1. Mean Reversion - ATR Filter (production/mean_rev_atr_filter.yaml)
2. Mean Reversion - Quiet Filter (production/mean_rev_quiet_filter.yaml)
3. Volume Spike Reversal (development, candidate for production)
"""

import sys
import os
import pandas as pd
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.adaptive_market_strategy import AdaptiveMarketStrategy
from strategies.volume_spike_reversal_strategy import VolumeSpikeReversalStrategy
from backtest.backtester import Backtester


def load_strategy_config(config_path):
    """Load strategy configuration from YAML."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def run_strategy_comparison(data_file):
    """Run all production strategies and compare results."""

    # Load data
    print(f"Loading data from {data_file}...")
    data = pd.read_csv(data_file, index_col=0, parse_dates=True)
    print(f"Loaded {len(data)} bars from {data.index[0]} to {data.index[-1]}")
    print("=" * 80)

    strategies = [
        {
            'name': 'Mean Rev - ATR Filter',
            'config_path': 'config/strategies/production/mean_rev_atr_filter.yaml',
            'class': AdaptiveMarketStrategy,
        },
        {
            'name': 'Mean Rev - Quiet Filter',
            'config_path': 'config/strategies/production/mean_rev_quiet_filter.yaml',
            'class': AdaptiveMarketStrategy,
        },
        {
            'name': 'Volume Spike Reversal',
            'config_path': 'config/strategies/development/volume_spike_reversal.yaml',
            'class': VolumeSpikeReversalStrategy,
        },
    ]

    # Backtester config for Volume Spike (simplified - no full config)
    simple_backtest_config = {
        'trading': {'initial_capital': 10000, 'position_size': 1, 'max_positions': 1},
        'contract': {'tick_size': 0.25, 'tick_value': 1.25, 'point_value': 5.0},
        'costs': {'commission_per_side': 0.60, 'slippage_ticks': 1},
        'risk': {'max_risk_per_trade_pct': 1.0, 'max_daily_loss_pct': 2.0},
    }

    results = []

    for strat_info in strategies:
        print(f"\nTesting: {strat_info['name']}")
        print("-" * 80)

        try:
            # Load config
            config = load_strategy_config(strat_info['config_path'])

            # Initialize strategy
            strategy = strat_info['class'](config['strategy'])

            # Generate signals FIRST
            print("Generating signals...")
            df_with_signals = strategy.generate_signals(data)

            # Initialize backtester with data that has signals
            # For production configs, use full config; for Volume Spike use simple config
            if 'production' in strat_info['config_path']:
                bt = Backtester(strategy, df_with_signals, config)
            else:
                bt = Backtester(strategy, df_with_signals, simple_backtest_config)

            # Run backtest (no arguments needed)
            print("Running backtest...")
            results_dict = bt.run()

            # Print summary
            print("\nResults:")
            print(f"  Total Return:    {results_dict['total_return']:>8.2f}%")
            print(f"  Win Rate:        {results_dict['win_rate']:>8.1f}%")
            print(f"  Profit Factor:   {results_dict['profit_factor']:>8.2f}")
            print(f"  Sharpe Ratio:    {results_dict['sharpe_ratio']:>8.2f}")
            print(f"  Max Drawdown:    {results_dict['max_drawdown']:>8.2f}%")
            print(f"  Total Trades:    {results_dict['total_trades']:>8}")
            print(f"  Avg Trade:       ${results_dict['avg_trade']:>8.2f}")
            print(f"  Winners:         {results_dict['winning_trades']:>8}")
            print(f"  Losers:          {results_dict['losing_trades']:>8}")

            # Store for comparison
            results.append({
                'Strategy': strat_info['name'],
                'Return%': results_dict['total_return'],
                'WinRate%': results_dict['win_rate'],
                'ProfitFactor': results_dict['profit_factor'],
                'SharpeRatio': results_dict['sharpe_ratio'],
                'MaxDD%': results_dict['max_drawdown'],
                'Trades': results_dict['total_trades'],
                'AvgTrade$': results_dict['avg_trade'],
                'Status': 'SUCCESS'
            })

        except Exception as e:
            print(f"ERROR running {strat_info['name']}: {e}")
            import traceback
            traceback.print_exc()

            # Store failed result for visibility
            results.append({
                'Strategy': strat_info['name'],
                'Return%': 0.0,
                'WinRate%': 0.0,
                'ProfitFactor': 0.0,
                'SharpeRatio': 0.0,
                'MaxDD%': 0.0,
                'Trades': 0,
                'AvgTrade$': 0.0,
                'Status': 'FAILED'
            })
            continue

    # Print comparison table
    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)

    if len(results) == 0:
        print("ERROR: No strategies completed successfully!")
        return None

    comparison_df = pd.DataFrame(results)
    print(comparison_df.to_string(index=False))

    # Rank strategies
    print("\n" + "=" * 80)
    print("RANKINGS")
    print("=" * 80)

    print("\nBy Return:")
    print(comparison_df.sort_values('Return%', ascending=False)[['Strategy', 'Return%']].to_string(index=False))

    print("\nBy Profit Factor:")
    print(comparison_df.sort_values('ProfitFactor', ascending=False)[['Strategy', 'ProfitFactor']].to_string(index=False))

    print("\nBy Sharpe Ratio:")
    print(comparison_df.sort_values('SharpeRatio', ascending=False)[['Strategy', 'SharpeRatio']].to_string(index=False))

    print("\nBy Max Drawdown (best = least negative):")
    print(comparison_df.sort_values('MaxDD%', ascending=False)[['Strategy', 'MaxDD%']].to_string(index=False))

    # Overall score
    print("\n" + "=" * 80)
    print("OVERALL SCORE (Return/|DD| * WR% * PF)")
    print("=" * 80)
    comparison_df['Score'] = (
        comparison_df['Return%'] /
        comparison_df['MaxDD%'].abs() *
        comparison_df['WinRate%'] / 100 *
        comparison_df['ProfitFactor']
    )
    print(comparison_df.sort_values('Score', ascending=False)[['Strategy', 'Score', 'Return%', 'MaxDD%']].to_string(index=False))

    return comparison_df


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Compare production strategies')
    parser.add_argument('--data-file', required=True, help='Path to MES data file')

    args = parser.parse_args()

    results_df = run_strategy_comparison(args.data_file)

    print("\n" + "=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)
