"""
Trade Performance Analyzer

Analyzes backtest trade results to find patterns:
- What works vs what doesn't
- Time-based performance
- Win/loss patterns
- Exit analysis
- Opportunities for improvement
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime

def analyze_trade_performance(trades_file):
    """Analyze trade performance from backtest results"""

    print("\n" + "="*60)
    print("TRADE PERFORMANCE ANALYSIS")
    print("="*60 + "\n")

    # Load trades
    print(f"Loading trades from {trades_file}...")
    df = pd.read_csv(trades_file)

    if 'entry_time' in df.columns:
        df['entry_time'] = pd.to_datetime(df['entry_time'])
    if 'exit_time' in df.columns:
        df['exit_time'] = pd.to_datetime(df['exit_time'])

    print(f"Loaded {len(df)} trades\n")

    # Basic stats
    winners = df[df['pnl'] > 0]
    losers = df[df['pnl'] < 0]

    print("="*60)
    print("OVERALL PERFORMANCE")
    print("="*60)
    print(f"Total Trades: {len(df)}")
    print(f"Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")
    print(f"Total P&L: ${df['pnl'].sum():.2f}")
    print(f"Average P&L: ${df['pnl'].mean():.2f}")
    print(f"Median P&L: ${df['pnl'].median():.2f}")

    print("\n" + "="*60)
    print("WIN/LOSS BREAKDOWN")
    print("="*60)
    print(f"Average Winner: ${winners['pnl'].mean():.2f}")
    print(f"Average Loser: ${losers['pnl'].mean():.2f}")
    print(f"Largest Winner: ${winners['pnl'].max():.2f}")
    print(f"Largest Loser: ${losers['pnl'].min():.2f}")
    print(f"Profit Factor: {winners['pnl'].sum() / abs(losers['pnl'].sum()):.2f}")

    # Direction analysis
    if 'direction' in df.columns:
        print("\n" + "="*60)
        print("DIRECTION ANALYSIS")
        print("="*60)

        for direction in df['direction'].unique():
            dir_trades = df[df['direction'] == direction]
            dir_winners = dir_trades[dir_trades['pnl'] > 0]
            dir_pnl = dir_trades['pnl'].sum()

            print(f"\n{direction} Trades:")
            print(f"  Count: {len(dir_trades)}")
            print(f"  Win Rate: {len(dir_winners)/len(dir_trades)*100:.1f}%")
            print(f"  Total P&L: ${dir_pnl:.2f}")
            print(f"  Avg P&L: ${dir_trades['pnl'].mean():.2f}")

    # Exit reason analysis
    if 'exit_reason' in df.columns:
        print("\n" + "="*60)
        print("EXIT REASON ANALYSIS")
        print("="*60)

        for reason in df['exit_reason'].unique():
            reason_trades = df[df['exit_reason'] == reason]
            reason_pnl = reason_trades['pnl'].sum()
            reason_avg = reason_trades['pnl'].mean()

            print(f"\n{reason}:")
            print(f"  Count: {len(reason_trades)} ({len(reason_trades)/len(df)*100:.1f}%)")
            print(f"  Total P&L: ${reason_pnl:+.2f}")
            print(f"  Avg P&L: ${reason_avg:+.2f}")

    # Time analysis
    if 'entry_time' in df.columns and not df['entry_time'].isna().all():
        print("\n" + "="*60)
        print("TIME-BASED ANALYSIS")
        print("="*60)

        df['entry_hour'] = df['entry_time'].dt.hour
        df['entry_day'] = df['entry_time'].dt.day_name()

        # Hourly performance
        print("\nPerformance by Hour:")
        hourly = df.groupby('entry_hour').agg({
            'pnl': ['sum', 'mean', 'count']
        }).round(2)

        for hour in sorted(df['entry_hour'].dropna().unique()):
            hour_trades = df[df['entry_hour'] == hour]
            hour_winners = hour_trades[hour_trades['pnl'] > 0]
            hour_pnl = hour_trades['pnl'].sum()
            hour_avg = hour_trades['pnl'].mean()
            hour_wr = len(hour_winners) / len(hour_trades) * 100 if len(hour_trades) > 0 else 0

            emoji = "✅" if hour_pnl > 0 else "❌"
            print(f"  {emoji} {int(hour):02d}:00 - Trades: {len(hour_trades)}, WR: {hour_wr:.0f}%, P&L: ${hour_pnl:+.2f}, Avg: ${hour_avg:+.2f}")

        # Day of week performance
        print("\nPerformance by Day of Week:")
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            day_trades = df[df['entry_day'] == day]
            if len(day_trades) > 0:
                day_winners = day_trades[day_trades['pnl'] > 0]
                day_pnl = day_trades['pnl'].sum()
                day_wr = len(day_winners) / len(day_trades) * 100

                emoji = "✅" if day_pnl > 0 else "❌"
                print(f"  {emoji} {day}: Trades: {len(day_trades)}, WR: {day_wr:.0f}%, P&L: ${day_pnl:+.2f}")

    # Duration analysis
    if 'duration_minutes' in df.columns:
        print("\n" + "="*60)
        print("TRADE DURATION ANALYSIS")
        print("="*60)
        print(f"Average Duration: {df['duration_minutes'].mean():.1f} minutes")
        print(f"Median Duration: {df['duration_minutes'].median():.1f} minutes")
        print(f"Shortest Trade: {df['duration_minutes'].min():.0f} minutes")
        print(f"Longest Trade: {df['duration_minutes'].max():.0f} minutes")

        # Duration vs profitability
        short_trades = df[df['duration_minutes'] < df['duration_minutes'].median()]
        long_trades = df[df['duration_minutes'] >= df['duration_minutes'].median()]

        print(f"\nShort Duration (<{df['duration_minutes'].median():.0f} min):")
        print(f"  Avg P&L: ${short_trades['pnl'].mean():+.2f}")
        print(f"  Win Rate: {(short_trades['pnl'] > 0).sum() / len(short_trades) * 100:.1f}%")

        print(f"\nLong Duration (>={df['duration_minutes'].median():.0f} min):")
        print(f"  Avg P&L: ${long_trades['pnl'].mean():+.2f}")
        print(f"  Win Rate: {(long_trades['pnl'] > 0).sum() / len(long_trades) * 100:.1f}%")

    # Consecutive losses
    print("\n" + "="*60)
    print("CONSECUTIVE LOSS ANALYSIS")
    print("="*60)

    max_consecutive = 0
    current_consecutive = 0
    max_consecutive_loss = 0
    current_consecutive_loss = 0

    for _, trade in df.iterrows():
        if trade['pnl'] < 0:
            current_consecutive += 1
            current_consecutive_loss += trade['pnl']
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
                max_consecutive_loss = current_consecutive_loss
        else:
            current_consecutive = 0
            current_consecutive_loss = 0

    print(f"Max Consecutive Losses: {max_consecutive}")
    print(f"Loss Amount: ${max_consecutive_loss:.2f}")

    # Top 5 winners and losers
    print("\n" + "="*60)
    print("TOP 5 WINNERS")
    print("="*60)
    top_winners = df.nlargest(min(5, len(winners)), 'pnl')
    for idx, trade in top_winners.iterrows():
        print(f"  ${trade['pnl']:+.2f} - {trade.get('direction', 'N/A')} - {trade.get('exit_reason', 'N/A')}")

    print("\n" + "="*60)
    print("TOP 5 LOSERS")
    print("="*60)
    top_losers = df.nsmallest(min(5, len(losers)), 'pnl')
    for idx, trade in top_losers.iterrows():
        print(f"  ${trade['pnl']:+.2f} - {trade.get('direction', 'N/A')} - {trade.get('exit_reason', 'N/A')}")

    print("\n" + "="*60)
    print("IMPROVEMENT OPPORTUNITIES")
    print("="*60)

    recommendations = []

    # Win rate
    win_rate = len(winners) / len(df) * 100
    if win_rate < 50:
        recommendations.append("⚠️  Win rate below 50% - Need better entry signals")
    elif win_rate < 55:
        recommendations.append("⚠️  Win rate marginal - Consider tighter entry filters")

    # Profit factor
    profit_factor = winners['pnl'].sum() / abs(losers['pnl'].sum()) if len(losers) > 0 else 999
    if profit_factor < 1.5:
        recommendations.append("⚠️  Low profit factor - Winners not big enough OR losers too large")

    # Stop loss analysis
    if 'exit_reason' in df.columns:
        stop_loss_trades = df[df['exit_reason'] == 'stop_loss']
        if len(stop_loss_trades) / len(df) > 0.5:
            recommendations.append("⚠️  >50% trades hit stop loss - Consider wider stops OR better entries")

    # Direction bias
    if 'direction' in df.columns:
        for direction in df['direction'].unique():
            dir_trades = df[df['direction'] == direction]
            dir_pnl = dir_trades['pnl'].sum()
            if dir_pnl < 0:
                recommendations.append(f"❌ {direction} trades losing money - Consider avoiding {direction}")

    # Time-based
    if 'entry_hour' in df.columns:
        for hour in sorted(df['entry_hour'].dropna().unique()):
            hour_trades = df[df['entry_hour'] == hour]
            hour_pnl = hour_trades['pnl'].sum()
            if len(hour_trades) >= 3 and hour_pnl < -50:
                recommendations.append(f"⏰ Hour {int(hour):02d}:00 losing money - Consider avoiding")

    if len(recommendations) == 0:
        recommendations.append("✅ Strategy looks good! Consider position sizing to increase returns")

    for rec in recommendations:
        print(f"  {rec}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trade_performance_analyzer.py <trades_csv>")
        print("Example: python trade_performance_analyzer.py logs/trades_20260215_223509.csv")
        sys.exit(1)

    trades_file = sys.argv[1]
    analyze_trade_performance(trades_file)
