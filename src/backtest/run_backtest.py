"""
Run Backtest - Main Entry Point

This script runs a complete backtest and generates results.
"""

import sys
import os
import yaml
import pandas as pd
import argparse
from datetime import datetime
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.volatility_breakout import VolatilityBreakoutStrategy
from backtest.backtester import Backtester


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        return None
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def load_data(filename: str) -> pd.DataFrame:
    """Load data from CSV file."""
    filepath = os.path.join('data/historical', filename)
    
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return None
    
    data = pd.read_csv(filepath, index_col=0, parse_dates=True)
    print(f"Loaded {len(data)} bars from {filepath}")
    
    return data


def print_summary(results: dict, config: dict):
    """Print backtest results summary."""
    metrics = results['metrics']
    
    print("\n" + "="*60)
    print("BACKTEST RESULTS SUMMARY")
    print("="*60)
    
    print(f"\nStrategy: {config['strategy']['name']}")
    print(f"Symbol: {config['trading']['symbol']}")
    print(f"Initial Capital: ${config['trading']['initial_capital']:,.2f}")
    print(f"Final Equity: ${metrics['final_equity']:,.2f}")
    
    print(f"\nPERFORMANCE")
    print(f"{'─'*60}")
    print(f"Total Return: {metrics['total_return_pct']:>10.2f}%")
    print(f"Total P&L: ${metrics['total_pnl']:>13,.2f}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:>11.2f}")
    print(f"Max Drawdown: {metrics['max_drawdown_pct']:>10.2f}%")
    
    print(f"\nTRADE STATISTICS")
    print(f"{'─'*60}")
    print(f"Total Trades: {metrics['total_trades']:>12}")
    print(f"Winning Trades: {metrics['winning_trades']:>10}")
    print(f"Losing Trades: {metrics['losing_trades']:>11}")
    print(f"Win Rate: {metrics['win_rate_pct']:>16.2f}%")
    
    print(f"\nPROFIT METRICS")
    print(f"{'─'*60}")
    print(f"Gross Profit: ${metrics['gross_profit']:>11,.2f}")
    print(f"Gross Loss: ${metrics['gross_loss']:>13,.2f}")
    print(f"Profit Factor: {metrics['profit_factor']:>11.2f}")
    print(f"Avg Trade: ${metrics['avg_trade']:>14,.2f}")
    print(f"Avg Win: ${metrics['avg_win']:>17,.2f}")
    print(f"Avg Loss: ${metrics['avg_loss']:>16,.2f}")
    
    print(f"\n{'='*60}\n")


def save_results(results: dict, config: dict, output_dir: str = 'logs'):
    """Save backtest results to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full results as JSON
    results_file = os.path.join(output_dir, f'backtest_{timestamp}.json')
    with open(results_file, 'w') as f:
        trades = results['trades']
        for trade in trades:
            if 'entry_time' in trade and trade['entry_time']:
                trade['entry_time'] = str(trade['entry_time'])
            if 'exit_time' in trade and trade['exit_time']:
                trade['exit_time'] = str(trade['exit_time'])
        
        json.dump({
            'config': config,
            'results': results
        }, f, indent=2, default=str)
    
    print(f"\nFull results saved to: {results_file}")
    
    # Save trades as CSV
    if results['trades']:
        trades_df = pd.DataFrame(results['trades'])
        trades_file = os.path.join(output_dir, f'trades_{timestamp}.csv')
        trades_df.to_csv(trades_file, index=False)
        print(f"Trades saved to: {trades_file}")
    
    # Save equity curve
    if results['equity_curve']:
        equity_df = pd.DataFrame(results['equity_curve'])
        equity_file = os.path.join(output_dir, f'equity_curve_{timestamp}.csv')
        equity_df.to_csv(equity_file, index=False)
        print(f"Equity curve saved to: {equity_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run strategy backtest')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--data-file', help='Specific data file to use')
    
    args = parser.parse_args()
    
    # Load configuration
    print("Loading configuration...")
    config = load_config(args.config)
    if config is None:
        return
    
    # Load data
    print("\nLoading historical data...")
    if args.data_file:
        data = load_data(args.data_file)
    else:
        data_dir = 'data/historical'
        if os.path.exists(data_dir):
            files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            if files:
                print(f"Found data files: {files}")
                data_file = files[0]
                print(f"Using: {data_file}")
                data = load_data(data_file)
            else:
                print("ERROR: No data files found in data/historical/")
                print("Run: python src/data/data_downloader.py --start 2023-01-01 --end 2024-12-31")
                return
        else:
            print("ERROR: data/historical/ directory not found")
            return
    
    if data is None:
        return
    
    print(f"Using {len(data)} bars for backtest")
    
    # Initialize strategy
    print("\nInitializing strategy...")
    strategy_name = config['strategy']['name']
    
    if strategy_name == 'volatility_breakout':
        strategy = VolatilityBreakoutStrategy(config['strategy'])
    else:
        print(f"ERROR: Unknown strategy: {strategy_name}")
        return
    
    print(f"Strategy: {strategy}")
    
    # Run backtest
    print("\n" + "="*60)
    backtester = Backtester(strategy, data, config)
    results = backtester.run()
    
    # Print summary
    print_summary(results, config)
    
    # Save results
    if config['backtest'].get('save_trades', True):
        save_results(results, config)
    
    print("\nBacktest complete! Check the logs/ directory for detailed results.")


if __name__ == "__main__":
    main()
