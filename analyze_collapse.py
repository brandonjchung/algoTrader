"""
Deep analysis of adaptive strategy trades
Find what went wrong after trade 90 when equity peaked
"""
import pandas as pd
import numpy as np

# Load trades from most recent backtest
trades_file = 'logs/trades_20260215_223509.csv'

try:
    df = pd.read_csv(trades_file)
    print(f"Loaded {len(df)} trades from adaptive strategy backtest\n")
except:
    print("ERROR: Could not find trades file")
    print("Run the backtest first to generate trades CSV")
    import sys
    sys.exit(1)

if 'entry_time' in df.columns:
    df['entry_time'] = pd.to_datetime(df['entry_time'])

print("="*60)
print("ANALYZING THE EQUITY CURVE COLLAPSE")
print("="*60)

# Calculate cumulative P&L
df['cumulative_pnl'] = df['pnl'].cumsum()
df['trade_number'] = range(1, len(df) + 1)

# Find the peak
peak_trade = df['cumulative_pnl'].idxmax()
peak_pnl = df.loc[peak_trade, 'cumulative_pnl']
peak_trade_num = df.loc[peak_trade, 'trade_number']

print(f"\n📈 Peak Performance:")
print(f"  Trade #{peak_trade_num}")
print(f"  Cumulative P&L: ${peak_pnl:.2f}")
print(f"  Date: {df.loc[peak_trade, 'entry_time']}")

# Analyze trades after peak
after_peak = df[df['trade_number'] > peak_trade_num].copy()
final_pnl = df['cumulative_pnl'].iloc[-1]
drawdown_from_peak = final_pnl - peak_pnl

print(f"\n📉 After Peak Performance:")
print(f"  Trades after peak: {len(after_peak)}")
print(f"  P&L after peak: ${after_peak['pnl'].sum():.2f}")
print(f"  Drawdown from peak: ${drawdown_from_peak:.2f}")

# Compare before/after peak
before_peak = df[df['trade_number'] <= peak_trade_num].copy()

print(f"\n{'='*60}")
print("BEFORE vs AFTER PEAK COMPARISON")
print("="*60)

print(f"\nBEFORE Peak (Trades 1-{peak_trade_num}):")
print(f"  Win Rate: {(before_peak['pnl'] > 0).sum() / len(before_peak) * 100:.1f}%")
print(f"  Avg P&L: ${before_peak['pnl'].mean():.2f}")
print(f"  Profit Factor: {before_peak[before_peak['pnl']>0]['pnl'].sum() / abs(before_peak[before_peak['pnl']<0]['pnl'].sum()):.2f}")

print(f"\nAFTER Peak (Trades {peak_trade_num+1}-{len(df)}):")
print(f"  Win Rate: {(after_peak['pnl'] > 0).sum() / len(after_peak) * 100:.1f}%")
print(f"  Avg P&L: ${after_peak['pnl'].mean():.2f}")
if len(after_peak[after_peak['pnl']<0]) > 0:
    print(f"  Profit Factor: {after_peak[after_peak['pnl']>0]['pnl'].sum() / abs(after_peak[after_peak['pnl']<0]['pnl'].sum()):.2f}")

# Direction analysis
print(f"\n{'='*60}")
print("DIRECTION ANALYSIS (After Peak)")
print("="*60)

if 'direction' in after_peak.columns:
    for direction in ['LONG', 'SHORT']:
        dir_trades = after_peak[after_peak['direction'] == direction]
        if len(dir_trades) > 0:
            dir_pnl = dir_trades['pnl'].sum()
            dir_wr = (dir_trades['pnl'] > 0).sum() / len(dir_trades) * 100
            print(f"\n{direction}:")
            print(f"  Count: {len(dir_trades)}")
            print(f"  Win Rate: {dir_wr:.1f}%")
            print(f"  Total P&L: ${dir_pnl:.2f}")
            print(f"  Avg P&L: ${dir_trades['pnl'].mean():.2f}")

# Exit reason analysis
print(f"\n{'='*60}")
print("EXIT REASON ANALYSIS (After Peak)")
print("="*60)

if 'exit_reason' in after_peak.columns:
    for reason in after_peak['exit_reason'].unique():
        reason_trades = after_peak[after_peak['exit_reason'] == reason]
        reason_pnl = reason_trades['pnl'].sum()
        print(f"\n{reason}:")
        print(f"  Count: {len(reason_trades)} ({len(reason_trades)/len(after_peak)*100:.1f}%)")
        print(f"  Total P&L: ${reason_pnl:.2f}")
        print(f"  Avg P&L: ${reason_trades['pnl'].mean():.2f}")

# Time period analysis
if 'entry_time' in after_peak.columns:
    print(f"\n{'='*60}")
    print("TIME PERIOD ANALYSIS (After Peak)")
    print("="*60)

    after_peak['month'] = after_peak['entry_time'].dt.to_period('M')

    print(f"\nP&L by Month (after peak):")
    for month in sorted(after_peak['month'].unique()):
        month_trades = after_peak[after_peak['month'] == month]
        month_pnl = month_trades['pnl'].sum()
        month_wr = (month_trades['pnl'] > 0).sum() / len(month_trades) * 100
        emoji = "✅" if month_pnl > 0 else "❌"
        print(f"  {emoji} {month}: {len(month_trades)} trades, WR {month_wr:.0f}%, P&L ${month_pnl:+.2f}")

print(f"\n{'='*60}")
print("KEY INSIGHTS")
print("="*60)

insights = []

# Win rate dropped?
before_wr = (before_peak['pnl'] > 0).sum() / len(before_peak) * 100
after_wr = (after_peak['pnl'] > 0).sum() / len(after_peak) * 100
if after_wr < before_wr - 5:
    insights.append(f"⚠️  Win rate dropped from {before_wr:.1f}% to {after_wr:.1f}%")

# Check if one direction failed
if 'direction' in after_peak.columns:
    for direction in ['LONG', 'SHORT']:
        dir_trades = after_peak[after_peak['direction'] == direction]
        if len(dir_trades) > 0:
            dir_pnl = dir_trades['pnl'].sum()
            if dir_pnl < -200:
                insights.append(f"❌ {direction} trades lost ${abs(dir_pnl):.2f} after peak")

# Check if stops dominate
if 'exit_reason' in after_peak.columns:
    stop_trades = after_peak[after_peak['exit_reason'] == 'stop_loss']
    if len(stop_trades) / len(after_peak) > 0.5:
        insights.append(f"🛑 {len(stop_trades)/len(after_peak)*100:.0f}% stopped out - stops too tight?")

# Specific bad months?
if 'entry_time' in after_peak.columns:
    after_peak['month'] = after_peak['entry_time'].dt.to_period('M')
    for month in after_peak['month'].unique():
        month_trades = after_peak[after_peak['month'] == month]
        month_pnl = month_trades['pnl'].sum()
        if month_pnl < -300:
            insights.append(f"💥 {month} was disaster month: ${month_pnl:.2f}")

if insights:
    for insight in insights:
        print(f"\n  {insight}")
else:
    print("\n  No obvious patterns found - need deeper analysis")

print(f"\n{'='*60}\n")
