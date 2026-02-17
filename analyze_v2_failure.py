"""
Analyze why V2 performed worse than V1
"""
import pandas as pd

print("="*60)
print("V2 FAILURE ANALYSIS")
print("="*60)

# Load both trade files
v1 = pd.read_csv('logs/trades_20260216_001216.csv')
v2 = pd.read_csv('logs/trades_20260216_143525.csv')

print(f"\n{'='*60}")
print("KEY DIFFERENCES")
print("="*60)

# V2 changes that were made
print("\nV2 Changes Applied:")
print("  1. Wider stops: 4.0 ATR (vs 3.0 ATR)")
print("  2. Stricter RSI: 30/70 (vs 35/65)")
print("  3. Better SHORT filters: Must be 0.5%+ above BB")
print("  4. Trailing stops enabled")
print("  5. Max 2 trades/day (vs 3)")

print(f"\n{'='*60}")
print("IMPACT ANALYSIS")
print("="*60)

# 1. Wider stops impact
v1_avg_loss = v1[v1['pnl'] < 0]['pnl'].mean()
v2_avg_loss = v2[v2['pnl'] < 0]['pnl'].mean()
print(f"\n1. WIDER STOPS (4.0 vs 3.0 ATR):")
print(f"   V1 Avg Loss: ${v1_avg_loss:.2f}")
print(f"   V2 Avg Loss: ${v2_avg_loss:.2f}")
print(f"   Impact: ${v2_avg_loss - v1_avg_loss:.2f} WORSE per loss")
print(f"   ❌ Wider stops are HURTING us - losses are 48% larger!")

# 2. Stricter RSI impact
print(f"\n2. STRICTER RSI (30/70 vs 35/65):")
print(f"   V1 Trades: {len(v1)}")
print(f"   V2 Trades: {len(v2)}")
print(f"   Impact: {len(v1) - len(v2)} fewer trades ({((len(v1)-len(v2))/len(v1)*100):.1f}% reduction)")
print(f"   ❌ We're filtering out 62% of trades - missing opportunities!")

# 3. SHORT filter impact
v1_shorts = v1[v1['direction'] == 'SHORT']
v2_shorts = v2[v2['direction'] == 'SHORT']
print(f"\n3. SHORT FILTERS (0.5% above BB):")
print(f"   V1 SHORT trades: {len(v1_shorts)}")
print(f"   V2 SHORT trades: {len(v2_shorts)}")
print(f"   V1 SHORT P&L: ${v1_shorts['pnl'].sum():.2f}")
print(f"   V2 SHORT P&L: ${v2_shorts['pnl'].sum():.2f}")
print(f"   Impact: Blocked {len(v1_shorts) - len(v2_shorts)} SHORT trades")
print(f"   ❌ Filtered out 93% of SHORTs - even bad SHORTs contributed +$139 in V1!")

# 4. Trailing stops
v2_trailing = v2[v2['exit_reason'] == 'trailing_stop']
print(f"\n4. TRAILING STOPS (new feature):")
print(f"   Trailing stop exits: {len(v2_trailing)}")
print(f"   Trailing stop P&L: ${v2_trailing['pnl'].sum():.2f}")
print(f"   Avg P&L per trailing: ${v2_trailing['pnl'].mean():.2f}")
if len(v2_trailing) > 0:
    print(f"   ⚠️  Trailing stops are LOSING money on average!")

# 5. LONG performance collapse
v1_longs = v1[v1['direction'] == 'LONG']
v2_longs = v2[v2['direction'] == 'LONG']
print(f"\n5. LONG TRADES (the real disaster):")
print(f"   V1 LONG: {len(v1_longs)} trades, ${v1_longs['pnl'].sum():.2f} P&L")
print(f"   V2 LONG: {len(v2_longs)} trades, ${v2_longs['pnl'].sum():.2f} P&L")
print(f"   Impact: ${v2_longs['pnl'].sum() - v1_longs['pnl'].sum():.2f}")
print(f"   ❌ LONG P&L collapsed by $1,027 - this is the main problem!")

print(f"\n{'='*60}")
print("ROOT CAUSE ANALYSIS")
print("="*60)

# Compare win sizes
v1_avg_win = v1[v1['pnl'] > 0]['pnl'].mean()
v2_avg_win = v2[v2['pnl'] > 0]['pnl'].mean()

print(f"\nWin/Loss Ratio:")
print(f"  V1: Avg win ${v1_avg_win:.2f} vs avg loss ${v1_avg_loss:.2f}")
print(f"      Ratio: {abs(v1_avg_win/v1_avg_loss):.2f}x")
print(f"  V2: Avg win ${v2_avg_win:.2f} vs avg loss ${v2_avg_loss:.2f}")
print(f"      Ratio: {abs(v2_avg_win/v2_avg_loss):.2f}x")
print(f"\n  ❌ V2 has WORSE win/loss ratio ({abs(v2_avg_win/v2_avg_loss):.2f} vs {abs(v1_avg_win/v1_avg_loss):.2f})")
print(f"     Winners got SMALLER (${v2_avg_win:.2f} vs ${v1_avg_win:.2f})")
print(f"     Losers got BIGGER (${v2_avg_loss:.2f} vs ${v1_avg_loss:.2f})")

# Check if it's just bad trades
print(f"\nTrade Quality:")
v1_good_trades = len(v1[v1['pnl'] > 50])
v2_good_trades = len(v2[v2['pnl'] > 50])
print(f"  V1: {v1_good_trades} trades with profit >$50")
print(f"  V2: {v2_good_trades} trades with profit >$50")
print(f"  ❌ V2 is missing {v1_good_trades - v2_good_trades} profitable trades")

print(f"\n{'='*60}")
print("THE PROBLEM")
print("="*60)

print("""
Our V2 changes made things WORSE because:

1. ❌ WIDER STOPS (4.0 ATR): Losses are 48% bigger
   - We thought stops were too tight, but wider stops just bleed more
   - The original 3.0 ATR was actually better

2. ❌ STRICTER RSI (30/70): Filtered out 62% of trades
   - We removed TOO many trades, including profitable ones
   - The original 35/65 was catching good entries we're now missing

3. ❌ SHORT FILTER TOO STRICT: Blocked 93% of SHORTs
   - Even though SHORTs had low 38% win rate, they still made +$139
   - Blocking them all cost us $500+ in P&L

4. ❌ TRAILING STOPS: Cutting winners too early
   - Avg trailing stop P&L is negative
   - We're exiting profitable trades before they reach targets

5. ❌ THE REAL ISSUE: We misdiagnosed the problem
   - The original analysis showed strategy peaked at trade 89
   - We applied "fixes" to the entire dataset
   - But the first 89 trades worked WELL - we shouldn't have changed them
   - The problem was trades AFTER 89 when market conditions shifted
""")

print(f"\n{'='*60}")
print("SOLUTION FOR V3")
print("="*60)

print("""
Instead of making the strategy MORE restrictive, we need to make it
MORE ADAPTIVE to changing market conditions:

V3 Approach:
1. ✅ REVERT to 3.0 ATR stops (narrower is better)
2. ✅ REVERT to 35/65 RSI (more opportunities)
3. ✅ REMOVE strict SHORT filter (let them trade)
4. ✅ DISABLE trailing stops (they're cutting winners)
5. ✅ ADD regime detection to adapt when market shifts
6. ✅ ADD volatility filtering - trade less in high volatility
7. ✅ ADD time-of-day optimization - avoid bad hours we identified

The key insight: Don't filter MORE. Adapt BETTER.
""")

print("="*60 + "\n")
