"""
Debug ADX regime detection
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('data/historical/MES_5mins_2024-12-20_to_2026-02-13_REAL.csv', index_col=0, parse_dates=True)

# Ensure index is datetime
if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index, utc=True)
if hasattr(df.index, 'tz') and df.index.tz is not None:
    df.index = df.index.tz_localize(None)

# Calculate ADX
def calculate_adx(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    up_move = df['high'] - df['high'].shift()
    down_move = df['low'].shift() - df['low']

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()

    return adx

df['adx'] = calculate_adx(df, 14)
df['hour'] = df.index.hour

# Filter to allowed hours
allowed = df[df['hour'].isin([13, 16, 21])].copy()

print(f"\nTotal bars at allowed hours: {len(allowed)}")
print(f"\n{'='*60}")
print("ADX REGIME ANALYSIS")
print("="*60)

# Check ADX values
print(f"\nADX Statistics:")
print(f"  Min: {allowed['adx'].min():.2f}")
print(f"  Max: {allowed['adx'].max():.2f}")
print(f"  Mean: {allowed['adx'].mean():.2f}")
print(f"  Median: {allowed['adx'].median():.2f}")
print(f"  NaN count: {allowed['adx'].isna().sum()}")

# Regime classification with threshold 20
trending_threshold = 20
ranging_bars = allowed[allowed['adx'] < trending_threshold]
trending_bars = allowed[allowed['adx'] >= trending_threshold]

print(f"\nRegime Classification (ADX threshold = {trending_threshold}):")
print(f"  Ranging (ADX < {trending_threshold}): {len(ranging_bars)} bars ({len(ranging_bars)/len(allowed)*100:.1f}%)")
print(f"  Trending (ADX >= {trending_threshold}): {len(trending_bars)} bars ({len(trending_bars)/len(allowed)*100:.1f}%)")

print(f"\n{'='*60}")
print("THIS IS THE PROBLEM!")
print("="*60)

if len(ranging_bars) == 0:
    print("\n❌ NO RANGING BARS at allowed hours!")
    print("   Mean reversion code NEVER executes!")
    print("\n   SOLUTION: Lower ADX threshold or remove ADX filter entirely")
    print(f"   Try ADX threshold = {allowed['adx'].quantile(0.7):.0f} (70th percentile)")
elif len(ranging_bars) < len(allowed) * 0.5:
    print(f"\n⚠️  Only {len(ranging_bars)/len(allowed)*100:.1f}% classified as ranging!")
    print("   Most bars treated as trending, mean reversion rarely runs")
    print(f"\n   SOLUTION: Increase ADX threshold to {allowed['adx'].quantile(0.7):.0f}")
else:
    print(f"\n✅ {len(ranging_bars)/len(allowed)*100:.1f}% classified as ranging - looks good!")
