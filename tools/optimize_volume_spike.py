"""
Volume Spike Reversal - Parameter Optimization
==============================================
Systematically tests different parameter combinations to find optimal settings
for production deployment.

Current baseline (from initial test):
- Return: +6.95%
- Win Rate: 52.94%
- Profit Factor: 2.09
- Max Drawdown: -1.27%
- Trades: 51

Parameters to optimize:
1. volume_spike_threshold: [2.5, 3.0, 3.5, 4.0]
2. bb_std_mult: [1.5, 2.0, 2.5]
3. stop_loss_atr_multiple: [1.0, 1.5, 2.0]
4. take_profit_atr_multiple: [2.0, 2.5, 3.0]
"""

import sys
import os
import pandas as pd
import numpy as np
import yaml
from itertools import product

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.volume_spike_reversal_strategy import VolumeSpikeReversalStrategy
from backtest.backtester import Backtester


def run_optimization(data_file, output_file='optimization_results.csv'):
    """Run parameter optimization grid search."""

    # Load data
    print(f"Loading data from {data_file}...")
    data = pd.read_csv(data_file, index_col=0, parse_dates=True)
    print(f"Loaded {len(data)} bars from {data.index[0]} to {data.index[-1]}")

    # Parameter grid
    param_grid = {
        'volume_spike_threshold': [2.5, 3.0, 3.5, 4.0],
        'bb_std_mult': [1.5, 2.0, 2.5],
        'stop_loss_atr_multiple': [1.0, 1.5, 2.0],
        'take_profit_atr_multiple': [2.0, 2.5, 3.0, 3.5],
    }

    # Fixed parameters (not optimizing these)
    fixed_params = {
        'volume_period': 20,
        'bb_period': 20,
        'atr_period': 14,
        'min_atr_for_entry': 2.0,
        'max_atr_for_entry': 8.0,
        'allowed_hours': [14, 15, 16, 17, 18, 19, 20, 21],
        'max_trades_per_day': 4,
        'max_bars_in_trade': 24,
        'use_trailing_stop': False,
    }

    # Backtester config
    backtest_config = {
        'trading': {'initial_capital': 10000, 'position_size': 1, 'max_positions': 1},
        'contract': {'tick_size': 0.25, 'tick_value': 1.25, 'point_value': 5.0},
        'costs': {'commission_per_side': 0.60, 'slippage_ticks': 1},
        'risk': {'max_risk_per_trade_pct': 1.0, 'max_daily_loss_pct': 2.0},
    }

    # Generate all combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(product(*param_values))

    print(f"\nTesting {len(combinations)} parameter combinations...")
    print("=" * 80)

    results = []

    for i, combo in enumerate(combinations, 1):
        # Build config
        config = fixed_params.copy()
        for name, value in zip(param_names, combo):
            config[name] = value

        # Run backtest
        try:
            strategy = VolumeSpikeReversalStrategy(config)

            # Generate signals FIRST
            df_with_signals = strategy.generate_signals(data)

            # Initialize backtester with data that has signals
            bt = Backtester(strategy, df_with_signals, backtest_config)

            # Run backtest (no arguments needed)
            bt_results = bt.run()
            metrics = bt_results['metrics']

            # Store results
            result_row = {
                'combo_id': i,
                'volume_spike_threshold': config['volume_spike_threshold'],
                'bb_std_mult': config['bb_std_mult'],
                'stop_loss_atr_multiple': config['stop_loss_atr_multiple'],
                'take_profit_atr_multiple': config['take_profit_atr_multiple'],
                'total_return_pct': metrics['total_return_pct'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'profit_factor': metrics['profit_factor'],
                'win_rate': metrics['win_rate_pct'],
                'max_drawdown_pct': metrics['max_drawdown_pct'],
                'total_trades': metrics['total_trades'],
                'avg_trade_pnl': metrics['avg_trade'],
            }
            results.append(result_row)

            # Print progress every 10 combinations
            if i % 10 == 0 or i == len(combinations):
                print(f"Progress: {i}/{len(combinations)} combinations tested")
                if result_row['total_trades'] > 0:
                    print(f"  Last: Return={result_row['total_return_pct']:.2f}%, "
                          f"WR={result_row['win_rate']:.1f}%, "
                          f"PF={result_row['profit_factor']:.2f}, "
                          f"Trades={result_row['total_trades']}")

        except Exception as e:
            print(f"Error on combo {i}: {e}")
            continue

    # Convert to dataframe
    results_df = pd.DataFrame(results)

    # Save results
    results_df.to_csv(output_file, index=False)
    print(f"\nResults saved to {output_file}")

    # Print top performers
    print("\n" + "=" * 80)
    print("TOP 10 BY TOTAL RETURN")
    print("=" * 80)
    top_return = results_df.nlargest(10, 'total_return_pct')
    print(top_return.to_string(index=False))

    print("\n" + "=" * 80)
    print("TOP 10 BY PROFIT FACTOR")
    print("=" * 80)
    top_pf = results_df.nlargest(10, 'profit_factor')
    print(top_pf.to_string(index=False))

    print("\n" + "=" * 80)
    print("TOP 10 BY SHARPE RATIO")
    print("=" * 80)
    top_sharpe = results_df[results_df['sharpe_ratio'].notna()].nlargest(10, 'sharpe_ratio')
    print(top_sharpe.to_string(index=False))

    print("\n" + "=" * 80)
    print("BEST RISK-ADJUSTED (High Return, Low Drawdown, High Win Rate)")
    print("=" * 80)
    # Score: return / drawdown * win_rate * (1 + profit_factor)
    results_df['score'] = (
        results_df['total_return_pct'] /
        results_df['max_drawdown_pct'].abs() *
        results_df['win_rate'] / 100 *
        (1 + results_df['profit_factor'])
    )
    top_score = results_df.nlargest(10, 'score')
    print(top_score[['combo_id', 'volume_spike_threshold', 'bb_std_mult',
                     'stop_loss_atr_multiple', 'take_profit_atr_multiple',
                     'total_return_pct', 'profit_factor', 'win_rate',
                     'max_drawdown_pct', 'total_trades', 'score']].to_string(index=False))

    return results_df


def analyze_parameter_sensitivity(results_df):
    """Analyze how each parameter affects performance."""

    print("\n" + "=" * 80)
    print("PARAMETER SENSITIVITY ANALYSIS")
    print("=" * 80)

    param_cols = ['volume_spike_threshold', 'bb_std_mult',
                  'stop_loss_atr_multiple', 'take_profit_atr_multiple']

    for param in param_cols:
        print(f"\n{param.upper()}")
        print("-" * 60)
        grouped = results_df.groupby(param).agg({
            'total_return_pct': 'mean',
            'profit_factor': 'mean',
            'win_rate': 'mean',
            'max_drawdown_pct': 'mean',
            'total_trades': 'mean',
        }).round(2)
        print(grouped.to_string())


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Optimize Volume Spike Reversal parameters')
    parser.add_argument('--data-file', required=True, help='Path to MES data file')
    parser.add_argument('--output', default='optimization_results.csv',
                       help='Output CSV file for results')

    args = parser.parse_args()

    # Run optimization
    results_df = run_optimization(args.data_file, args.output)

    # Analyze sensitivity
    if len(results_df) > 0:
        analyze_parameter_sensitivity(results_df)

    print("\n" + "=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)
    print(f"Tested {len(results_df)} combinations")
    print(f"Results saved to: {args.output}")
