"""
Compare Adaptive Strategy V1 vs V2 Results
"""
import pandas as pd
import glob
import os

print("="*60)
print("ADAPTIVE STRATEGY V1 vs V2 COMPARISON")
print("="*60)

# Find most recent trades files
trades_files = sorted(glob.glob('logs/trades_*.csv'), key=os.path.getctime, reverse=True)

if len(trades_files) < 2:
    print("\nERROR: Need at least 2 trade files to compare")
    print("Run both v1 and v2 backtests first")
    exit(1)

print(f"\nComparing:")
print(f"  V2 (newer): {trades_files[0]}")
print(f"  V1 (older): {trades_files[1]}")
print()

# Load both
v2 = pd.read_csv(trades_files[0])
v1 = pd.read_csv(trades_files[1])

def analyze(df, name):
    total_pnl = df['pnl'].sum()
    win_rate = (df['pnl'] > 0).sum() / len(df) * 100

    wins = df[df['pnl'] > 0]['pnl'].sum()
    losses = abs(df[df['pnl'] < 0]['pnl'].sum())
    profit_factor = wins / losses if losses > 0 else 0

    avg_win = df[df['pnl'] > 0]['pnl'].mean() if len(df[df['pnl'] > 0]) > 0 else 0
    avg_loss = df[df['pnl'] < 0]['pnl'].mean() if len(df[df['pnl'] < 0]) > 0 else 0

    # Drawdown
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['cumulative_max'] = df['cumulative_pnl'].cummax()
    df['drawdown'] = df['cumulative_pnl'] - df['cumulative_max']
    max_dd = df['drawdown'].min()

    # Direction breakdown
    if 'direction' in df.columns:
        long_trades = df[df['direction'] == 'LONG']
        short_trades = df[df['direction'] == 'SHORT']
        long_pnl = long_trades['pnl'].sum() if len(long_trades) > 0 else 0
        short_pnl = short_trades['pnl'].sum() if len(short_trades) > 0 else 0
        long_wr = (long_trades['pnl'] > 0).sum() / len(long_trades) * 100 if len(long_trades) > 0 else 0
        short_wr = (short_trades['pnl'] > 0).sum() / len(short_trades) * 100 if len(short_trades) > 0 else 0
    else:
        long_trades = short_trades = pd.DataFrame()
        long_pnl = short_pnl = long_wr = short_wr = 0

    # Exit reasons
    if 'exit_reason' in df.columns:
        stop_loss_pct = (df['exit_reason'] == 'stop_loss').sum() / len(df) * 100
        take_profit_pct = (df['exit_reason'] == 'take_profit').sum() / len(df) * 100
        trailing_stop_pct = (df['exit_reason'] == 'trailing_stop').sum() / len(df) * 100
    else:
        stop_loss_pct = take_profit_pct = trailing_stop_pct = 0

    print(f"\n{name}:")
    print(f"  Trades: {len(df)}")
    print(f"  Total P&L: ${total_pnl:.2f}")
    print(f"  Return: {(total_pnl/10000)*100:.2f}%")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Profit Factor: {profit_factor:.2f}")
    print(f"  Avg Win: ${avg_win:.2f}")
    print(f"  Avg Loss: ${avg_loss:.2f}")
    print(f"  Max Drawdown: ${max_dd:.2f}")
    print(f"\n  Direction:")
    print(f"    LONG: {len(long_trades)} trades, WR {long_wr:.1f}%, P&L ${long_pnl:.2f}")
    print(f"    SHORT: {len(short_trades)} trades, WR {short_wr:.1f}%, P&L ${short_pnl:.2f}")
    print(f"\n  Exits:")
    print(f"    Stop Loss: {stop_loss_pct:.1f}%")
    print(f"    Take Profit: {take_profit_pct:.1f}%")
    print(f"    Trailing Stop: {trailing_stop_pct:.1f}%")

    return {
        'trades': len(df),
        'pnl': total_pnl,
        'return_pct': (total_pnl/10000)*100,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_dd': max_dd,
        'long_trades': len(long_trades),
        'short_trades': len(short_trades),
        'long_wr': long_wr,
        'short_wr': short_wr,
    }

print("\n" + "="*60)
print("DETAILED BREAKDOWN")
print("="*60)

v1_stats = analyze(v1, "V1 (Original)")
v2_stats = analyze(v2, "V2 (Improved)")

print("\n" + "="*60)
print("IMPROVEMENTS (V2 vs V1)")
print("="*60)

improvements = []

if v2_stats['return_pct'] > v1_stats['return_pct']:
    improvements.append(f"✅ Return: {v2_stats['return_pct']:.2f}% vs {v1_stats['return_pct']:.2f}% (+{v2_stats['return_pct']-v1_stats['return_pct']:.2f}%)")
else:
    improvements.append(f"❌ Return: {v2_stats['return_pct']:.2f}% vs {v1_stats['return_pct']:.2f}% ({v2_stats['return_pct']-v1_stats['return_pct']:.2f}%)")

if v2_stats['win_rate'] > v1_stats['win_rate']:
    improvements.append(f"✅ Win Rate: {v2_stats['win_rate']:.1f}% vs {v1_stats['win_rate']:.1f}% (+{v2_stats['win_rate']-v1_stats['win_rate']:.1f}%)")
else:
    improvements.append(f"❌ Win Rate: {v2_stats['win_rate']:.1f}% vs {v1_stats['win_rate']:.1f}% ({v2_stats['win_rate']-v1_stats['win_rate']:.1f}%)")

if v2_stats['profit_factor'] > v1_stats['profit_factor']:
    improvements.append(f"✅ Profit Factor: {v2_stats['profit_factor']:.2f} vs {v1_stats['profit_factor']:.2f}")
else:
    improvements.append(f"❌ Profit Factor: {v2_stats['profit_factor']:.2f} vs {v1_stats['profit_factor']:.2f}")

if v2_stats['max_dd'] > v1_stats['max_dd']:  # Less negative = better
    improvements.append(f"✅ Max Drawdown: ${v2_stats['max_dd']:.2f} vs ${v1_stats['max_dd']:.2f}")
else:
    improvements.append(f"❌ Max Drawdown: ${v2_stats['max_dd']:.2f} vs ${v1_stats['max_dd']:.2f}")

if v2_stats['short_wr'] > v1_stats['short_wr']:
    improvements.append(f"✅ SHORT Win Rate: {v2_stats['short_wr']:.1f}% vs {v1_stats['short_wr']:.1f}% (was the problem!)")
else:
    improvements.append(f"⚠️  SHORT Win Rate: {v2_stats['short_wr']:.1f}% vs {v1_stats['short_wr']:.1f}%")

if v2_stats['trades'] < v1_stats['trades']:
    improvements.append(f"✅ Fewer trades: {v2_stats['trades']} vs {v1_stats['trades']} (less overtrading)")
else:
    improvements.append(f"⚠️  More trades: {v2_stats['trades']} vs {v1_stats['trades']}")

for imp in improvements:
    print(f"\n  {imp}")

print("\n" + "="*60)
print("VERDICT")
print("="*60)

# Count improvements
checkmarks = sum([1 for imp in improvements if '✅' in imp])
xmarks = sum([1 for imp in improvements if '❌' in imp])

if checkmarks >= 4:
    print("\n✅ V2 is a clear improvement! Better on most metrics.")
elif checkmarks >= 2:
    print("\n⚠️  V2 shows some improvements but needs more work")
else:
    print("\n❌ V2 didn't improve - need to rethink approach")

print(f"\nKey targets for V3:")
if v2_stats['return_pct'] < 12:
    print(f"  - Increase returns to 12-15% (current: {v2_stats['return_pct']:.2f}%)")
if v2_stats['win_rate'] < 52:
    print(f"  - Improve win rate to 52%+ (current: {v2_stats['win_rate']:.1f}%)")
if v2_stats['profit_factor'] < 1.8:
    print(f"  - Improve profit factor to 1.8+ (current: {v2_stats['profit_factor']:.2f})")
if v2_stats['max_dd'] < -800:
    print(f"  - Reduce max drawdown below -$800 (current: ${v2_stats['max_dd']:.2f})")

print("\n" + "="*60 + "\n")
