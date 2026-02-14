"""
Trade Analysis Tool
Analyzes backtest results to identify problems and opportunities for improvement
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys
import os

def analyze_trades(trades_csv_path, equity_csv_path=None):
    """Comprehensive trade analysis."""

    print("\n" + "="*80)
    print("COMPREHENSIVE TRADE ANALYSIS")
    print("="*80 + "\n")

    # Load trades
    trades = pd.read_csv(trades_csv_path)
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['exit_time'] = pd.to_datetime(trades['exit_time'])

    print(f"Total Trades: {len(trades)}")
    print(f"Date Range: {trades['entry_time'].min()} to {trades['exit_time'].max()}\n")

    # Basic stats
    winners = trades[trades['pnl'] > 0]
    losers = trades[trades['pnl'] < 0]

    print("="*80)
    print("BASIC STATISTICS")
    print("="*80)
    print(f"Winning Trades: {len(winners)} ({len(winners)/len(trades)*100:.1f}%)")
    print(f"Losing Trades: {len(losers)} ({len(losers)/len(trades)*100:.1f}%)")
    print(f"Average Win: ${winners['pnl'].mean():.2f}")
    print(f"Average Loss: ${losers['pnl'].mean():.2f}")
    print(f"Largest Win: ${winners['pnl'].max():.2f}")
    print(f"Largest Loss: ${losers['pnl'].min():.2f}")
    print(f"Total P&L: ${trades['pnl'].sum():.2f}\n")

    # Exit reason analysis
    print("="*80)
    print("EXIT REASON BREAKDOWN")
    print("="*80)
    exit_reasons = trades.groupby('exit_reason').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean'
    }).round(2)
    print(exit_reasons)
    print()

    # Direction analysis
    print("="*80)
    print("DIRECTION ANALYSIS")
    print("="*80)
    long_trades = trades[trades['direction'] == 'LONG']
    short_trades = trades[trades['direction'] == 'SHORT']

    print(f"\nLONG Trades: {len(long_trades)}")
    print(f"  Win Rate: {(long_trades['pnl'] > 0).sum() / len(long_trades) * 100:.1f}%")
    print(f"  Avg P&L: ${long_trades['pnl'].mean():.2f}")
    print(f"  Total P&L: ${long_trades['pnl'].sum():.2f}")

    print(f"\nSHORT Trades: {len(short_trades)}")
    print(f"  Win Rate: {(short_trades['pnl'] > 0).sum() / len(short_trades) * 100:.1f}%")
    print(f"  Avg P&L: ${short_trades['pnl'].mean():.2f}")
    print(f"  Total P&L: ${short_trades['pnl'].sum():.2f}\n")

    # Time-based analysis
    print("="*80)
    print("TIME-BASED ANALYSIS")
    print("="*80)

    trades['entry_hour'] = trades['entry_time'].dt.hour
    trades['entry_month'] = trades['entry_time'].dt.to_period('M')
    trades['entry_year'] = trades['entry_time'].dt.year

    # By hour
    print("\nPerformance by Entry Hour:")
    hourly = trades.groupby('entry_hour').agg({
        'pnl': ['count', 'sum', 'mean']
    }).round(2)
    print(hourly)

    # By year
    print("\nPerformance by Year:")
    yearly = trades.groupby('entry_year').agg({
        'pnl': ['count', 'sum', 'mean']
    })
    yearly['win_rate'] = trades.groupby('entry_year').apply(
        lambda x: (x['pnl'] > 0).sum() / len(x) * 100
    )
    print(yearly.round(2))

    # Consecutive losses analysis
    print("\n" + "="*80)
    print("CONSECUTIVE LOSS ANALYSIS (CRITICAL FOR DRAWDOWN)")
    print("="*80)

    consecutive_losses = []
    current_streak = 0
    max_streak = 0
    max_streak_loss = 0
    current_streak_loss = 0

    for _, trade in trades.iterrows():
        if trade['pnl'] < 0:
            current_streak += 1
            current_streak_loss += trade['pnl']
            if current_streak > max_streak:
                max_streak = current_streak
                max_streak_loss = current_streak_loss
        else:
            if current_streak > 0:
                consecutive_losses.append({
                    'streak': current_streak,
                    'total_loss': current_streak_loss
                })
            current_streak = 0
            current_streak_loss = 0

    print(f"\nMax Consecutive Losses: {max_streak}")
    print(f"Loss from Max Streak: ${max_streak_loss:.2f}")

    if consecutive_losses:
        loss_df = pd.DataFrame(consecutive_losses)
        print(f"\nNumber of Losing Streaks >= 5: {len(loss_df[loss_df['streak'] >= 5])}")
        print(f"Number of Losing Streaks >= 10: {len(loss_df[loss_df['streak'] >= 10])}")

        if len(loss_df[loss_df['streak'] >= 5]) > 0:
            print("\nWorst Losing Streaks:")
            worst = loss_df.nlargest(5, 'total_loss')
            for idx, row in worst.iterrows():
                print(f"  {int(row['streak'])} losses = ${row['total_loss']:.2f}")

    # MAE/MFE Analysis
    print("\n" + "="*80)
    print("MAE/MFE ANALYSIS (Entry/Exit Quality)")
    print("="*80)

    # For winners: how close to stop?
    winners_with_mae = winners[winners['mae'].notna()]
    if len(winners_with_mae) > 0:
        print(f"\nWinning Trades:")
        print(f"  Average MAE: ${winners_with_mae['mae'].mean():.2f}")
        print(f"  Average MFE: ${winners_with_mae['mfe'].mean():.2f}")

        # How often did winners almost hit stop?
        stop_distances = []
        for _, trade in winners_with_mae.iterrows():
            if trade['direction'] == 'LONG':
                stop_distance = trade['entry_price'] - trade['stop_loss']
                mae_pct = abs(trade['mae']) / stop_distance if stop_distance > 0 else 0
            else:
                stop_distance = trade['stop_loss'] - trade['entry_price']
                mae_pct = abs(trade['mae']) / stop_distance if stop_distance > 0 else 0
            stop_distances.append(mae_pct)

        almost_stopped = sum(1 for x in stop_distances if x > 0.8)
        print(f"  Winners that almost hit stop (>80%): {almost_stopped} ({almost_stopped/len(winners)*100:.1f}%)")

    # For losers: how close to target?
    losers_with_mfe = losers[losers['mfe'].notna()]
    if len(losers_with_mfe) > 0:
        print(f"\nLosing Trades:")
        print(f"  Average MAE: ${losers_with_mfe['mae'].mean():.2f}")
        print(f"  Average MFE: ${losers_with_mfe['mfe'].mean():.2f}")

        # How often did losers almost reach target?
        target_distances = []
        for _, trade in losers_with_mfe.iterrows():
            if trade['direction'] == 'LONG':
                target_distance = trade['take_profit'] - trade['entry_price']
                mfe_pct = trade['mfe'] / target_distance if target_distance > 0 else 0
            else:
                target_distance = trade['entry_price'] - trade['take_profit']
                mfe_pct = trade['mfe'] / target_distance if target_distance > 0 else 0
            target_distances.append(mfe_pct)

        almost_won = sum(1 for x in target_distances if x > 0.8)
        print(f"  Losers that almost hit target (>80%): {almost_won} ({almost_won/len(losers)*100:.1f}%)")

    # Equity curve analysis
    if equity_csv_path and os.path.exists(equity_csv_path):
        print("\n" + "="*80)
        print("EQUITY CURVE ANALYSIS")
        print("="*80)

        equity = pd.read_csv(equity_csv_path)
        equity['time'] = pd.to_datetime(equity['time'])

        # Find worst drawdown period
        max_dd_idx = equity['drawdown_pct'].idxmin()
        max_dd_row = equity.loc[max_dd_idx]

        print(f"\nWorst Drawdown: {max_dd_row['drawdown_pct']:.2f}%")
        print(f"Occurred at: {max_dd_row['time']}")
        print(f"Equity at that point: ${max_dd_row['equity']:.2f}")

        # Find trades during worst drawdown
        dd_date = max_dd_row['time']
        trades_near_dd = trades[
            (trades['entry_time'] >= dd_date - pd.Timedelta(days=30)) &
            (trades['entry_time'] <= dd_date + pd.Timedelta(days=30))
        ]

        print(f"\nTrades around worst drawdown (±30 days):")
        print(f"  Total trades: {len(trades_near_dd)}")
        print(f"  Win rate: {(trades_near_dd['pnl'] > 0).sum() / len(trades_near_dd) * 100:.1f}%")
        print(f"  Total P&L: ${trades_near_dd['pnl'].sum():.2f}")
        print(f"  Average P&L: ${trades_near_dd['pnl'].mean():.2f}")

    # Recommendations
    print("\n" + "="*80)
    print("AUTOMATED RECOMMENDATIONS")
    print("="*80)

    recommendations = []

    # Check for directional bias
    if abs(long_trades['pnl'].sum() - short_trades['pnl'].sum()) > 1000:
        if long_trades['pnl'].sum() > short_trades['pnl'].sum():
            recommendations.append("⚠️ LONG trades significantly more profitable - consider LONG-only strategy")
        else:
            recommendations.append("⚠️ SHORT trades significantly more profitable - consider SHORT-only strategy")

    # Check for time-of-day issues
    hourly_pnl = trades.groupby('entry_hour')['pnl'].sum()
    worst_hours = hourly_pnl.nsmallest(3)
    if worst_hours.min() < -500:
        recommendations.append(f"⚠️ Avoid trading during hours: {list(worst_hours.index)} (worst performance)")

    # Check stop loss effectiveness
    stopped_out = trades[trades['exit_reason'] == 'stop_loss']
    if len(stopped_out) > 0:
        stop_win_rate = (stopped_out['pnl'] > 0).sum() / len(stopped_out) * 100
        if stop_win_rate < 5:  # Should never win when stopped out
            recommendations.append("✓ Stop losses working correctly")
        else:
            recommendations.append(f"⚠️ {stop_win_rate:.1f}% of stop losses still profitable - stops may be too tight")

    # Check time exits
    time_exits = trades[trades['exit_reason'] == 'time_exit']
    if len(time_exits) > len(trades) * 0.3:
        avg_time_exit_pnl = time_exits['pnl'].mean()
        if avg_time_exit_pnl < 0:
            recommendations.append(f"⚠️ {len(time_exits)} time exits ({len(time_exits)/len(trades)*100:.1f}%) with avg loss ${avg_time_exit_pnl:.2f} - consider tighter stops or better entries")
        else:
            recommendations.append(f"✓ Time exits profitable (${avg_time_exit_pnl:.2f} avg) - good trend identification")

    # Check for consecutive losses
    if max_streak >= 10:
        recommendations.append(f"🚨 CRITICAL: {max_streak} consecutive losses - MUST add circuit breaker")
    elif max_streak >= 5:
        recommendations.append(f"⚠️ {max_streak} consecutive losses - add circuit breaker to stop after 5 losses")

    # Check profit factor
    gross_profit = winners['pnl'].sum()
    gross_loss = abs(losers['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    if profit_factor < 1.2:
        recommendations.append(f"⚠️ Profit factor {profit_factor:.2f} too low - need better entries or exits")

    if recommendations:
        print("\n" + "\n".join(recommendations))
    else:
        print("\n✓ No major issues detected")

    print("\n" + "="*80 + "\n")

    return {
        'total_trades': len(trades),
        'win_rate': len(winners) / len(trades) * 100,
        'profit_factor': profit_factor,
        'max_consecutive_losses': max_streak,
        'recommendations': recommendations
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trade_analyzer.py <trades_csv_file> [equity_csv_file]")
        sys.exit(1)

    trades_file = sys.argv[1]
    equity_file = sys.argv[2] if len(sys.argv) > 2 else None

    analyze_trades(trades_file, equity_file)
