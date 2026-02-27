"""
Volume Spike Reversal - Live Trading Runner
===========================================
Runs the optimized Volume Spike Reversal strategy on live/paper IB account.

Usage:
    python tools/run_volume_spike_live.py --mode paper    # Paper trading
    python tools/run_volume_spike_live.py --mode live     # Live trading (REAL MONEY)

Strategy Performance (3-month backtest):
    Return: +11.23%, WR: 61.90%, PF: 3.20, MaxDD: -0.87%
    Avg: $26.75/trade, ~3 trades/week
"""

import sys
import os
import argparse
from datetime import datetime
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.volume_spike_reversal_strategy import VolumeSpikeReversalStrategy


def load_config():
    """Load production config."""
    config_path = 'config/strategies/production/volume_spike_reversal.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def run_live_trading(mode='paper'):
    """
    Run Volume Spike Reversal in live/paper mode.

    Args:
        mode: 'paper' or 'live'
    """

    print("=" * 80)
    print(f"VOLUME SPIKE REVERSAL - {mode.upper()} MODE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load config
    config = load_config()
    print("Configuration loaded:")
    print(f"  Volume Spike Threshold: {config['strategy']['volume_spike_threshold']}x")
    print(f"  BB Period: {config['strategy']['bb_period']}, Std: {config['strategy']['bb_std_mult']}")
    print(f"  Stop Loss: {config['strategy']['stop_loss_atr_multiple']}x ATR")
    print(f"  Take Profit: {config['strategy']['take_profit_atr_multiple']}x ATR")
    print(f"  Trading Hours: {config['strategy']['allowed_hours']}")
    print(f"  Max Trades/Day: {config['strategy']['max_trades_per_day']}")
    print()

    # Initialize strategy
    strategy = VolumeSpikeReversalStrategy(config['strategy'])
    print(f"Strategy initialized: {strategy.get_name()}")
    print()

    # TODO: Connect to IB and start live trading loop
    print("=" * 80)
    print("NEXT STEPS TO IMPLEMENT:")
    print("=" * 80)
    print("1. Connect to Interactive Brokers (TWS/Gateway)")
    print("2. Subscribe to MES 5-minute bars")
    print("3. On each new bar:")
    print("   - Calculate indicators")
    print("   - Check for Volume Spike signal")
    print("   - If signal: Place market order with stop/target")
    print("4. Monitor open positions:")
    print("   - Check if stop hit → exit")
    print("   - Check if target hit → exit")
    print("   - Check if max bars held → exit")
    print("5. Log all trades to file")
    print()
    print("=" * 80)
    print("WARNING: Live trading implementation requires:")
    print("=" * 80)
    print("- IB API connection handling")
    print("- Real-time data feed")
    print("- Order management system")
    print("- Position tracking")
    print("- Error handling & reconnection logic")
    print("- Trade logging & performance tracking")
    print()
    print("Recommendation: Start with paper trading for 1-2 months")
    print("to validate the strategy on fresh, unseen data.")
    print("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run Volume Spike Reversal strategy live'
    )
    parser.add_argument(
        '--mode',
        choices=['paper', 'live'],
        default='paper',
        help='Trading mode: paper or live (default: paper)'
    )

    args = parser.parse_args()

    if args.mode == 'live':
        print("\n" + "!" * 80)
        print("WARNING: LIVE MODE - REAL MONEY AT RISK")
        print("!" * 80)
        response = input("Are you sure you want to trade with real money? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)

    run_live_trading(args.mode)
