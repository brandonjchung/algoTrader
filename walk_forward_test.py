"""
Walk-Forward Testing Framework

Implements systematic testing per claude.md methodology:
- Split data into train/test/validate
- Test strategy on each period
- Ensure no look-ahead bias
- Provide statistical validation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import subprocess
import json
import os
from pathlib import Path


class WalkForwardTester:
    """
    Walk-forward testing framework for systematic strategy validation.
    """

    def __init__(self, data_file, config_file):
        """
        Initialize walk-forward tester.

        Args:
            data_file: Path to historical data CSV
            config_file: Path to strategy config YAML
        """
        self.data_file = data_file
        self.config_file = config_file
        self.results = []

        # Load data to determine date ranges
        df = pd.read_csv(f"data/historical/{data_file}")
        # Handle timezone-aware IB data
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        # Convert to timezone-naive for easier handling
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)

        self.start_date = df['timestamp'].min()
        self.end_date = df['timestamp'].max()
        self.total_days = (self.end_date - self.start_date).days

        print(f"Data loaded: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Total days: {self.total_days}")

    def split_data(self, train_months=6, test_months=3, validate_months=3):
        """
        Split data into train/test/validate periods.

        Args:
            train_months: Months for training period
            test_months: Months for testing period
            validate_months: Months for validation period

        Returns:
            dict with period definitions
        """
        total_months = train_months + test_months + validate_months

        # Calculate split points
        train_end = self.start_date + timedelta(days=train_months * 30)
        test_end = train_end + timedelta(days=test_months * 30)
        validate_end = test_end + timedelta(days=validate_months * 30)

        # Ensure we don't exceed data range
        if validate_end > self.end_date:
            print("⚠️  Warning: Not enough data for full split")
            # Adjust proportionally
            total_available_days = self.total_days
            train_days = int(total_available_days * (train_months / total_months))
            test_days = int(total_available_days * (test_months / total_months))

            train_end = self.start_date + timedelta(days=train_days)
            test_end = train_end + timedelta(days=test_days)
            validate_end = self.end_date

        periods = {
            'train': {
                'start': self.start_date,
                'end': train_end,
                'purpose': 'Optimize parameters here (can iterate)'
            },
            'test': {
                'start': train_end,
                'end': test_end,
                'purpose': 'Validate performance (compare variants)'
            },
            'validate': {
                'start': test_end,
                'end': validate_end,
                'purpose': 'FINAL check (use ONCE only)'
            }
        }

        return periods

    def create_period_data(self, start_date, end_date, output_file):
        """
        Create a data file for a specific period.

        Args:
            start_date: Start date
            end_date: End date
            output_file: Output filename
        """
        # Load full dataset
        df = pd.read_csv(f"data/historical/{self.data_file}")
        # Handle timezone-aware IB data
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        # Convert to timezone-naive for easier handling
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)

        # Filter to period
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        df_period = df[mask]

        # Save
        output_path = f"data/historical/{output_file}"
        df_period.to_csv(output_path, index=False)

        print(f"  Created {output_file}: {len(df_period)} bars")
        return output_path

    def run_backtest(self, period_name, period_data_file):
        """
        Run backtest on a specific period.

        Args:
            period_name: Name of period (train/test/validate)
            period_data_file: Data file for this period

        Returns:
            dict with results
        """
        print(f"\n{'='*60}")
        print(f"Running backtest: {period_name.upper()}")
        print(f"{'='*60}")

        # Run backtest
        cmd = [
            'python', 'src/backtest/run_backtest.py',
            '--config', self.config_file,
            '--data-file', period_data_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Backtest failed: {result.stderr}")
            return None

        # Find most recent results file
        logs_dir = Path('logs')
        result_files = sorted(logs_dir.glob('backtest_*.json'), key=os.path.getmtime, reverse=True)

        if not result_files:
            print("❌ No results file found")
            return None

        # Load results
        with open(result_files[0], 'r') as f:
            results = json.load(f)

        # Extract key metrics
        metrics = {
            'period': period_name,
            'total_return_pct': results['performance']['total_return_pct'],
            'sharpe_ratio': results['performance']['sharpe_ratio'],
            'max_drawdown_pct': results['performance']['max_drawdown_pct'],
            'total_trades': results['trades']['total_trades'],
            'win_rate': results['trades']['win_rate'],
            'profit_factor': results['trades']['profit_factor'],
            'avg_win': results['trades']['avg_win'],
            'avg_loss': results['trades']['avg_loss']
        }

        return metrics

    def walk_forward_test(self):
        """
        Execute full walk-forward test.

        Returns:
            dict with results from all periods
        """
        print("\n" + "="*60)
        print("WALK-FORWARD TESTING")
        print("="*60)
        print(f"\nStrategy: {self.config_file}")
        print(f"Data: {self.data_file}")

        # Split data
        periods = self.split_data()

        print(f"\n{'='*60}")
        print("DATA SPLITS")
        print("="*60)

        for name, period in periods.items():
            days = (period['end'] - period['start']).days
            print(f"\n{name.upper()}:")
            print(f"  {period['start'].date()} to {period['end'].date()} ({days} days)")
            print(f"  Purpose: {period['purpose']}")

        # Create period-specific data files
        print(f"\n{'='*60}")
        print("CREATING PERIOD DATA FILES")
        print("="*60)

        period_files = {}
        for name, period in periods.items():
            filename = f"wf_{name}_{self.data_file}"
            self.create_period_data(period['start'], period['end'], filename)
            period_files[name] = filename

        # Run backtests on each period
        results = {}
        for name in ['train', 'test', 'validate']:
            metrics = self.run_backtest(name, period_files[name])
            if metrics:
                results[name] = metrics

        # Print summary
        self.print_summary(results)

        # Clean up period files
        print(f"\n{'='*60}")
        print("CLEANING UP")
        print("="*60)
        for filename in period_files.values():
            os.remove(f"data/historical/{filename}")
            print(f"  Removed {filename}")

        return results

    def print_summary(self, results):
        """Print walk-forward test summary."""
        print(f"\n{'='*60}")
        print("WALK-FORWARD TEST RESULTS")
        print("="*60)

        # Table header
        print(f"\n{'Period':<12} {'Return':<10} {'Sharpe':<8} {'Trades':<8} {'Win Rate':<10} {'PF':<8}")
        print("-" * 60)

        # Print results
        for period in ['train', 'test', 'validate']:
            if period not in results:
                continue

            r = results[period]
            print(f"{period.capitalize():<12} "
                  f"{r['total_return_pct']:>6.2f}%   "
                  f"{r['sharpe_ratio']:>6.2f}  "
                  f"{r['total_trades']:>6}  "
                  f"{r['win_rate']:>6.1f}%     "
                  f"{r['profit_factor']:>6.2f}")

        # Analysis
        print(f"\n{'='*60}")
        print("ANALYSIS")
        print("="*60)

        if 'train' in results and 'test' in results:
            train_ret = results['train']['total_return_pct']
            test_ret = results['test']['total_return_pct']
            degradation = train_ret - test_ret

            print(f"\nTrain → Test Degradation: {degradation:.2f}%")

            if degradation < 2:
                print("  ✅ Excellent - strategy generalizes well")
            elif degradation < 5:
                print("  ✅ Good - acceptable degradation")
            elif degradation < 10:
                print("  ⚠️  Warning - significant degradation, possible overfitting")
            else:
                print("  ❌ FAIL - severe degradation, likely overfit to train period")

            # Sharpe comparison
            train_sharpe = results['train']['sharpe_ratio']
            test_sharpe = results['test']['sharpe_ratio']

            print(f"\nSharpe Ratio Stability:")
            print(f"  Train: {train_sharpe:.2f}")
            print(f"  Test:  {test_sharpe:.2f}")

            if test_sharpe >= train_sharpe * 0.8:
                print("  ✅ Sharpe maintained - robust strategy")
            else:
                print("  ❌ Sharpe collapsed - not robust")

        if 'validate' in results:
            print(f"\nValidation Period (FINAL CHECK):")
            val_ret = results['validate']['total_return_pct']
            val_sharpe = results['validate']['sharpe_ratio']

            print(f"  Return: {val_ret:.2f}%")
            print(f"  Sharpe: {val_sharpe:.2f}")

            if val_ret > 5 and val_sharpe > 1.0:
                print("  ✅ PASS - Strategy approved for live trading consideration")
            elif val_ret > 0 and val_sharpe > 0.5:
                print("  ⚠️  MARGINAL - Strategy needs improvement")
            else:
                print("  ❌ FAIL - Strategy not ready for live trading")

        print("\n" + "="*60 + "\n")


def main():
    """Run walk-forward test."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python walk_forward_test.py <config_file> <data_file>")
        print("\nExample:")
        print("  python walk_forward_test.py config_adaptive_market.yaml MES_5mins_2025-02-14_to_2026-02-13_REAL.csv")
        sys.exit(1)

    config_file = sys.argv[1]
    data_file = sys.argv[2]

    tester = WalkForwardTester(data_file, config_file)
    results = tester.walk_forward_test()


if __name__ == '__main__':
    main()
