"""
Volume Spike Reversal - Forward Testing
========================================
Tests Volume Spike Reversal on FRESH data to validate it works on unseen data.

This is the critical step before live trading:
1. Download fresh MES data (NEW period, not used in optimization)
2. Run Volume Spike with production parameters
3. Compare results to backtest expectations

Expected backtest performance (Nov 2025 - Feb 2026):
    Return: +11.23%, WR: 61.90%, PF: 3.20, MaxDD: -0.87%

Usage:
    python tools/forward_test_volume_spike.py --data-file data/historical/MES_NEW_PERIOD.csv
"""

import sys
import os
import argparse
import yaml
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.volume_spike_reversal_strategy import VolumeSpikeReversalStrategy
from backtest.backtester import Backtester


def load_config():
    """Load production config."""
    config_path = 'config/strategies/production/volume_spike_reversal.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def forward_test(data_file):
    """Run forward test on fresh data."""

    print("=" * 80)
    print("VOLUME SPIKE REVERSAL - FORWARD TEST")
    print("=" * 80)
    print()

    # Load config
    config = load_config()
    print("Production Config Loaded:")
    print(f"  Volume Spike: {config['strategy']['volume_spike_threshold']}x")
    print(f"  BB: {config['strategy']['bb_period']} period, {config['strategy']['bb_std_mult']} std")
    print(f"  Stop: {config['strategy']['stop_loss_atr_multiple']}x ATR")
    print(f"  Target: {config['strategy']['take_profit_atr_multiple']}x ATR")
    print()

    # Load fresh data
    print(f"Loading FRESH data from: {data_file}")
    data = pd.read_csv(data_file, index_col=0, parse_dates=True)
    print(f"  Period: {data.index[0]} to {data.index[-1]}")
    print(f"  Bars: {len(data)}")
    print()

    # Initialize strategy
    strategy = VolumeSpikeReversalStrategy(config['strategy'])

    # Generate signals
    print("Generating signals...")
    df_with_signals = strategy.generate_signals(data)

    # Run backtest
    print("Running forward test...")
    bt = Backtester(strategy, df_with_signals, config)
    results = bt.run()
    metrics = results['metrics']

    # Print results
    print()
    print("=" * 80)
    print("FORWARD TEST RESULTS")
    print("=" * 80)
    print(f"Total Return:    {metrics['total_return_pct']:>8.2f}%")
    print(f"Win Rate:        {metrics['win_rate_pct']:>8.1f}%")
    print(f"Profit Factor:   {metrics['profit_factor']:>8.2f}")
    print(f"Sharpe Ratio:    {metrics['sharpe_ratio']:>8.2f}")
    print(f"Max Drawdown:    {metrics['max_drawdown_pct']:>8.2f}%")
    print(f"Total Trades:    {metrics['total_trades']:>8}")
    print(f"Avg Trade:       ${metrics['avg_trade']:>8.2f}")
    print(f"Winners:         {metrics['winning_trades']:>8}")
    print(f"Losers:          {metrics['losing_trades']:>8}")
    print()

    # Compare to backtest expectations
    print("=" * 80)
    print("COMPARISON TO BACKTEST")
    print("=" * 80)
    backtest_metrics = {
        'Return': 11.23,
        'Win Rate': 61.90,
        'Profit Factor': 3.20,
        'Max DD': -0.87,
    }

    forward_metrics = {
        'Return': metrics['total_return_pct'],
        'Win Rate': metrics['win_rate_pct'],
        'Profit Factor': metrics['profit_factor'],
        'Max DD': metrics['max_drawdown_pct'],
    }

    print(f"{'Metric':<15} {'Backtest':>12} {'Forward':>12} {'Diff':>12}")
    print("-" * 80)
    for key in backtest_metrics:
        bt_val = backtest_metrics[key]
        fwd_val = forward_metrics[key]
        diff = fwd_val - bt_val
        diff_str = f"{diff:+.2f}"
        print(f"{key:<15} {bt_val:>12.2f} {fwd_val:>12.2f} {diff_str:>12}")

    print()
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)

    # Check if forward test is within reasonable range
    checks = []

    if forward_metrics['Return'] >= backtest_metrics['Return'] * 0.5:
        checks.append(("✓", "Return is at least 50% of backtest"))
    else:
        checks.append(("✗", f"Return too low: {forward_metrics['Return']:.2f}% vs expected {backtest_metrics['Return']:.2f}%"))

    if forward_metrics['Win Rate'] >= 50:
        checks.append(("✓", "Win Rate above 50%"))
    else:
        checks.append(("✗", f"Win Rate too low: {forward_metrics['Win Rate']:.1f}%"))

    if forward_metrics['Profit Factor'] >= 1.5:
        checks.append(("✓", "Profit Factor above 1.5"))
    else:
        checks.append(("✗", f"Profit Factor too low: {forward_metrics['Profit Factor']:.2f}"))

    if forward_metrics['Max DD'] > -2.0:
        checks.append(("✓", "Max Drawdown acceptable (< 2%)"))
    else:
        checks.append(("✗", f"Max Drawdown too large: {forward_metrics['Max DD']:.2f}%"))

    if metrics['total_trades'] >= 30:
        checks.append(("✓", f"Sufficient trades: {metrics['total_trades']}"))
    else:
        checks.append(("⚠", f"Low trade count: {metrics['total_trades']} (need more data)"))

    for status, message in checks:
        print(f"{status} {message}")

    print()

    # Final recommendation
    all_passed = all(status == "✓" for status, _ in checks)
    if all_passed:
        print("=" * 80)
        print("✓ FORWARD TEST PASSED - Strategy validates on fresh data")
        print("=" * 80)
        print("Next step: Run on paper account for 1-2 months to validate live execution")
    else:
        print("=" * 80)
        print("⚠ FORWARD TEST ISSUES - Review results before live trading")
        print("=" * 80)
        print("Strategy may be overfitted or market regime has changed.")
        print("Consider collecting more data or re-optimizing parameters.")

    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Forward test Volume Spike Reversal')
    parser.add_argument('--data-file', required=True, help='Path to FRESH MES data file')

    args = parser.parse_args()

    if not os.path.exists(args.data_file):
        print(f"ERROR: Data file not found: {args.data_file}")
        sys.exit(1)

    forward_test(args.data_file)
