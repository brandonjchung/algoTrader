"""
Run All Production Strategies

Backtests every config in config/strategies/production/ against the same data file.
Prints a summary comparison table at the end.

Usage:
    python tools/run_all_production.py <data-file>
    python tools/run_all_production.py MES_5mins_2025-02-14_to_2026-02-13_REAL.csv
"""

import sys
import os
import glob
import subprocess
import json
import argparse
from datetime import datetime

PRODUCTION_DIR = os.path.join('config', 'strategies', 'production')
LOGS_DIR = 'logs'


def find_data_file(name):
    """Resolve data file path."""
    path = os.path.join('data', 'historical', name)
    if os.path.exists(path):
        return name
    if os.path.exists(name):
        return os.path.basename(name)
    return None


def get_latest_backtest_json(after_timestamp):
    """Find the most recent backtest JSON created after a given time."""
    pattern = os.path.join(LOGS_DIR, 'backtest_*.json')
    files = sorted(glob.glob(pattern), reverse=True)
    for f in files:
        mtime = os.path.getmtime(f)
        if mtime >= after_timestamp:
            return f
    return None


def run_backtest(config_path, data_file):
    """Run a single backtest and return the results JSON path."""
    before = datetime.now().timestamp()

    cmd = [
        sys.executable, 'src/backtest/run_backtest.py',
        '--config', config_path,
        '--data-file', data_file
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=os.getcwd()
    )

    if result.returncode != 0:
        return None, result.stderr

    # Find the JSON file that was just created
    json_path = get_latest_backtest_json(before)
    return json_path, result.stdout


def load_results(json_path):
    """Load metrics from a backtest JSON."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data.get('results', {}).get('metrics', {})


def main():
    parser = argparse.ArgumentParser(description='Run all production strategies')
    parser.add_argument('data_file', help='Data file name in data/historical/')
    parser.add_argument('--configs', nargs='*', help='Specific configs to run (default: all)')
    args = parser.parse_args()

    data_file = find_data_file(args.data_file)
    if data_file is None:
        print(f"ERROR: Data file not found: {args.data_file}")
        sys.exit(1)

    # Find all production configs
    if args.configs:
        configs = [os.path.join(PRODUCTION_DIR, c) for c in args.configs]
    else:
        configs = sorted(glob.glob(os.path.join(PRODUCTION_DIR, '*.yaml')))

    if not configs:
        print(f"ERROR: No configs found in {PRODUCTION_DIR}/")
        sys.exit(1)

    print(f"{'='*70}")
    print(f"RUNNING ALL PRODUCTION STRATEGIES")
    print(f"{'='*70}")
    print(f"Data: {data_file}")
    print(f"Configs: {len(configs)}")
    for c in configs:
        print(f"  - {os.path.basename(c)}")
    print(f"{'='*70}\n")

    # Run each backtest
    results = []
    for i, config_path in enumerate(configs, 1):
        config_name = os.path.basename(config_path).replace('.yaml', '')
        print(f"\n[{i}/{len(configs)}] Running {config_name}...")
        print(f"{'-'*50}")

        json_path, output = run_backtest(config_path, data_file)

        if json_path is None:
            print(f"  FAILED: {output[:200] if output else 'Unknown error'}")
            results.append({
                'config': config_name,
                'status': 'FAILED',
            })
            continue

        metrics = load_results(json_path)
        results.append({
            'config': config_name,
            'status': 'OK',
            'return_pct': metrics.get('total_return_pct', 0),
            'win_rate': metrics.get('win_rate_pct', 0),
            'profit_factor': metrics.get('profit_factor', 0),
            'max_dd_pct': metrics.get('max_drawdown_pct', 0),
            'trades': metrics.get('total_trades', 0),
            'sharpe': metrics.get('sharpe_ratio', 0),
            'avg_trade': metrics.get('avg_trade', 0),
            'json_path': json_path,
        })
        print(f"  Return: {metrics.get('total_return_pct', 0):+.2f}% | "
              f"PF: {metrics.get('profit_factor', 0):.2f} | "
              f"WR: {metrics.get('win_rate_pct', 0):.1f}% | "
              f"Trades: {metrics.get('total_trades', 0)}")

    # Summary table
    print(f"\n\n{'='*70}")
    print(f"PRODUCTION STRATEGY COMPARISON")
    print(f"{'='*70}")
    print(f"{'Config':<30} {'Return':>8} {'PF':>7} {'WR':>7} {'MaxDD':>8} {'Trades':>7} {'Sharpe':>7}")
    print(f"{'-'*70}")

    for r in sorted(results, key=lambda x: x.get('return_pct', -999), reverse=True):
        if r['status'] == 'FAILED':
            print(f"{r['config']:<30} {'FAILED':>8}")
            continue
        print(f"{r['config']:<30} {r['return_pct']:>+7.2f}% {r['profit_factor']:>7.2f} "
              f"{r['win_rate']:>6.1f}% {r['max_dd_pct']:>7.2f}% {r['trades']:>7} {r['sharpe']:>7.2f}")

    print(f"{'='*70}")
    print(f"\nAll results saved to logs/. View in dashboard: python -m streamlit run dashboard.py")


if __name__ == '__main__':
    main()
