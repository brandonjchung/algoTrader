"""
Rolling Walk-Forward Optimizer

Slides a train/test window across the full dataset to measure strategy
robustness over time. Unlike the single-shot walk_forward_test.py, this
tests EVERY period, not just the first 12 months.

Usage:
  python tools/rolling_walk_forward.py <config> <data-file> [--train-months 6] [--test-months 3]

Output:
  - Per-window results (return, WR, PF, trades)
  - Aggregate statistics (mean, std, win-rate-of-windows)
  - Parameter stability assessment
  - Monthly equity contribution chart (text)
"""

import sys
import os
import subprocess
import json
import re
import argparse
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def load_data(data_file):
    """Load data and return DataFrame with parsed timestamps."""
    path = os.path.join('data/historical', data_file)
    df = pd.read_csv(path)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        df.set_index('timestamp', inplace=True)
    else:
        df.index = pd.to_datetime(df.index)
    return df


def create_period_file(full_df, start, end, data_file):
    """Write a temp data file for a date range. Returns the filename."""
    mask = (full_df.index >= start) & (full_df.index < end)
    period_df = full_df[mask]
    if len(period_df) == 0:
        return None, 0

    fname = f"wf_rolling_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
    path = os.path.join('data/historical', fname)
    period_df.to_csv(path)
    return fname, len(period_df)


def run_backtest(config, data_file):
    """Run backtest, return parsed metrics dict."""
    cmd = [sys.executable, 'src/backtest/run_backtest.py',
           '--config', config, '--data-file', data_file]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    return parse_metrics(output)


def parse_metrics(output):
    """Extract metrics from backtest stdout."""
    patterns = {
        'return': r'Total Return:\s+([-\d.]+)%',
        'sharpe': r'Sharpe Ratio:\s+([-\d.]+)',
        'max_dd': r'Max Drawdown:\s+([-\d.]+)%',
        'trades': r'Total Trades:\s+(\d+)',
        'win_rate': r'Win Rate:\s+([-\d.]+)%',
        'pf': r'Profit Factor:\s+([-\d.]+)',
        'pnl': r'Total P&L: \$\s*([-\d.,]+)',
    }
    m = {}
    for key, pat in patterns.items():
        match = re.search(pat, output)
        if match:
            val = match.group(1).replace(',', '')
            m[key] = float(val) if '.' in val else int(val)
        else:
            m[key] = 0
    return m


def cleanup_file(fname):
    """Remove a temp data file."""
    path = os.path.join('data/historical', fname)
    if os.path.exists(path):
        os.remove(path)


def main():
    parser = argparse.ArgumentParser(description='Rolling Walk-Forward Test')
    parser.add_argument('config', help='Strategy config YAML path')
    parser.add_argument('data_file', help='Data file in data/historical/')
    parser.add_argument('--train-months', type=int, default=6,
                        help='Training window in months (default: 6)')
    parser.add_argument('--test-months', type=int, default=3,
                        help='Test window in months (default: 3)')
    parser.add_argument('--step-months', type=int, default=3,
                        help='Step size for sliding window (default: 3)')
    args = parser.parse_args()

    print("=" * 70)
    print("ROLLING WALK-FORWARD TEST")
    print("=" * 70)
    print(f"Config:  {args.config}")
    print(f"Data:    {args.data_file}")
    print(f"Windows: {args.train_months}mo train / {args.test_months}mo test, "
          f"sliding {args.step_months}mo per step")

    # Load data
    full_df = load_data(args.data_file)
    data_start = full_df.index.min()
    data_end = full_df.index.max()
    print(f"Data range: {data_start.date()} to {data_end.date()}")

    # Generate rolling windows
    window_size = timedelta(days=(args.train_months + args.test_months) * 30)
    step = timedelta(days=args.step_months * 30)
    train_days = timedelta(days=args.train_months * 30)

    windows = []
    current_start = data_start
    while current_start + window_size <= data_end + timedelta(days=15):
        train_end = current_start + train_days
        test_end = train_end + timedelta(days=args.test_months * 30)
        if test_end > data_end + timedelta(days=15):
            break
        windows.append({
            'train_start': current_start,
            'train_end': train_end,
            'test_start': train_end,
            'test_end': min(test_end, data_end),
        })
        current_start += step

    print(f"Generated {len(windows)} rolling windows\n")

    # Run each window
    train_results = []
    test_results = []

    for i, w in enumerate(windows):
        label = f"Window {i+1}/{len(windows)}"
        train_label = f"{w['train_start'].strftime('%Y-%m')} to {w['train_end'].strftime('%Y-%m')}"
        test_label = f"{w['test_start'].strftime('%Y-%m')} to {w['test_end'].strftime('%Y-%m')}"

        print(f"--- {label}: Train {train_label} | Test {test_label} ---")

        # Create period data files
        train_file, train_bars = create_period_file(
            full_df, w['train_start'], w['train_end'], args.data_file)
        test_file, test_bars = create_period_file(
            full_df, w['test_start'], w['test_end'], args.data_file)

        if not train_file or not test_file or train_bars < 100 or test_bars < 100:
            print(f"  Skipped: insufficient data (train={train_bars}, test={test_bars})")
            if train_file: cleanup_file(train_file)
            if test_file: cleanup_file(test_file)
            continue

        # Run backtests
        train_m = run_backtest(args.config, train_file)
        test_m = run_backtest(args.config, test_file)

        train_m['window'] = i + 1
        train_m['period'] = train_label
        test_m['window'] = i + 1
        test_m['period'] = test_label

        train_results.append(train_m)
        test_results.append(test_m)

        # Print summary line
        t_ret = test_m.get('return', 0)
        t_trades = test_m.get('trades', 0)
        t_wr = test_m.get('win_rate', 0)
        t_pf = test_m.get('pf', 0)
        tr_ret = train_m.get('return', 0)
        status = "[OK]" if t_ret > 0 else "[--]"
        print(f"  Train: {tr_ret:>6.2f}% ({train_m.get('trades',0)}T)  "
              f"Test: {t_ret:>6.2f}% ({t_trades}T, WR {t_wr:.0f}%, PF {t_pf:.2f}) {status}")

        # Cleanup
        cleanup_file(train_file)
        cleanup_file(test_file)

    # Aggregate results
    if not test_results:
        print("\nNo windows produced results.")
        return

    print("\n" + "=" * 70)
    print("ROLLING WALK-FORWARD SUMMARY")
    print("=" * 70)

    test_returns = [r['return'] for r in test_results]
    test_trades = [r['trades'] for r in test_results]
    test_pfs = [r['pf'] for r in test_results if r['trades'] > 0]
    test_wrs = [r['win_rate'] for r in test_results if r['trades'] > 0]
    train_returns = [r['return'] for r in train_results]

    profitable_windows = sum(1 for r in test_returns if r > 0)
    total_windows = len(test_returns)

    print(f"\nTest Period Results ({total_windows} windows):")
    print(f"  {'Metric':<25} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8}")
    print(f"  {'-'*57}")
    print(f"  {'Return %':<25} {np.mean(test_returns):>7.2f}% {np.std(test_returns):>7.2f}% "
          f"{min(test_returns):>7.2f}% {max(test_returns):>7.2f}%")
    if test_trades:
        print(f"  {'Trades':<25} {np.mean(test_trades):>8.1f} {np.std(test_trades):>8.1f} "
              f"{min(test_trades):>8d} {max(test_trades):>8d}")
    if test_pfs:
        print(f"  {'Profit Factor':<25} {np.mean(test_pfs):>8.2f} {np.std(test_pfs):>8.2f} "
              f"{min(test_pfs):>8.2f} {max(test_pfs):>8.2f}")
    if test_wrs:
        print(f"  {'Win Rate %':<25} {np.mean(test_wrs):>7.2f}% {np.std(test_wrs):>7.2f}% "
              f"{min(test_wrs):>7.2f}% {max(test_wrs):>7.2f}%")

    print(f"\n  Profitable windows: {profitable_windows}/{total_windows} "
          f"({profitable_windows/total_windows*100:.0f}%)")

    # Train vs Test degradation
    degradations = [train_returns[i] - test_returns[i] for i in range(len(test_returns))]
    print(f"\n  Avg train->test degradation: {np.mean(degradations):.2f}%")
    if np.mean(degradations) > 5:
        print("  [WARN] High degradation suggests overfitting risk")
    elif np.mean(degradations) < 0:
        print("  [OK] Test outperforms train on average (rare, good sign)")
    else:
        print("  [OK] Acceptable degradation")

    # Consistency score
    if profitable_windows >= total_windows * 0.6 and np.mean(test_pfs) > 1.0:
        print(f"\n  ASSESSMENT: CONSISTENT - profitable in {profitable_windows}/{total_windows} "
              f"windows with avg PF {np.mean(test_pfs):.2f}")
    elif profitable_windows >= total_windows * 0.4:
        print(f"\n  ASSESSMENT: INCONSISTENT - profitable in only {profitable_windows}/{total_windows} "
              f"windows. Strategy works in some regimes but not all.")
    else:
        print(f"\n  ASSESSMENT: UNRELIABLE - profitable in only {profitable_windows}/{total_windows} "
              f"windows. Not suitable for live trading.")

    # Per-window detail table
    print(f"\n{'Window':<8} {'Train Period':<22} {'Train Ret':>10} {'Test Ret':>10} "
          f"{'Test Trades':>12} {'Test PF':>8}")
    print("-" * 70)
    for i in range(len(test_results)):
        tr = train_results[i]
        te = test_results[i]
        print(f"{te['window']:<8} {te['period']:<22} {tr['return']:>9.2f}% {te['return']:>9.2f}% "
              f"{te['trades']:>12} {te['pf']:>8.2f}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
