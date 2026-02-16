"""
Debug script to see what's happening at allowed hours
"""
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('data/historical/MES_5mins_2024-12-20_to_2026-02-13_REAL.csv', index_col=0, parse_dates=True)

# Ensure index is datetime (fix for IB data format with timezone)
if not isinstance(df.index, pd.DatetimeIndex):
    df.index = pd.to_datetime(df.index, utc=True)

# Remove timezone info if present (convert to timezone-naive)
if hasattr(df.index, 'tz') and df.index.tz is not None:
    df.index = df.index.tz_localize(None)

# Calculate RSI
def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Calculate indicators
df['rsi'] = calc_rsi(df['close'])
df['bb_middle'] = df['close'].rolling(window=20).mean()
bb_std = df['close'].rolling(window=20).std()
df['bb_upper'] = df['bb_middle'] + (2.0 * bb_std)
df['bb_lower'] = df['bb_middle'] - (2.0 * bb_std)

# Add hour
df['hour'] = df.index.hour

# Filter to allowed hours
allowed = df[df['hour'].isin([13, 16, 21])].copy()

print(f"\nTotal bars at allowed hours (13, 16, 21): {len(allowed)}")
print(f"Date range: {allowed.index[0]} to {allowed.index[-1]}")

# Check conditions
print("\n" + "="*60)
print("CHECKING ENTRY CONDITIONS")
print("="*60)

# Mean reversion LONG conditions
oversold = allowed['rsi'] < 30
at_lower_bb = allowed['close'] < allowed['bb_lower']
long_setups = oversold & at_lower_bb

print(f"\nMean Reversion LONG setups:")
print(f"  RSI < 30: {oversold.sum()} bars")
print(f"  Price < BB Lower: {at_lower_bb.sum()} bars")
print(f"  BOTH conditions: {long_setups.sum()} bars")

# Mean reversion SHORT conditions
overbought = allowed['rsi'] > 70
at_upper_bb = allowed['close'] > allowed['bb_upper']
short_setups = overbought & at_upper_bb

print(f"\nMean Reversion SHORT setups:")
print(f"  RSI > 70: {overbought.sum()} bars")
print(f"  Price > BB Upper: {at_upper_bb.sum()} bars")
print(f"  BOTH conditions: {short_setups.sum()} bars")

# Show some examples
print("\n" + "="*60)
print("RSI DISTRIBUTION at allowed hours:")
print("="*60)
print(f"Min RSI: {allowed['rsi'].min():.2f}")
print(f"Max RSI: {allowed['rsi'].max():.2f}")
print(f"Mean RSI: {allowed['rsi'].mean():.2f}")
print(f"Median RSI: {allowed['rsi'].median():.2f}")

print(f"\nRSI < 40: {(allowed['rsi'] < 40).sum()} bars ({(allowed['rsi'] < 40).sum()/len(allowed)*100:.1f}%)")
print(f"RSI < 35: {(allowed['rsi'] < 35).sum()} bars ({(allowed['rsi'] < 35).sum()/len(allowed)*100:.1f}%)")
print(f"RSI < 30: {(allowed['rsi'] < 30).sum()} bars ({(allowed['rsi'] < 30).sum()/len(allowed)*100:.1f}%)")

print(f"\nRSI > 60: {(allowed['rsi'] > 60).sum()} bars ({(allowed['rsi'] > 60).sum()/len(allowed)*100:.1f}%)")
print(f"RSI > 65: {(allowed['rsi'] > 65).sum()} bars ({(allowed['rsi'] > 65).sum()/len(allowed)*100:.1f}%)")
print(f"RSI > 70: {(allowed['rsi'] > 70).sum()} bars ({(allowed['rsi'] > 70).sum()/len(allowed)*100:.1f}%)")

# If we loosen to RSI 40/60
print("\n" + "="*60)
print("IF WE LOOSEN TO RSI 40/60:")
print("="*60)
oversold_loose = allowed['rsi'] < 40
long_setups_loose = oversold_loose & at_lower_bb
print(f"LONG setups (RSI<40 + BB): {long_setups_loose.sum()} bars")

overbought_loose = allowed['rsi'] > 60
short_setups_loose = overbought_loose & at_upper_bb
print(f"SHORT setups (RSI>60 + BB): {short_setups_loose.sum()} bars")

print(f"\nTotal potential trades: {long_setups_loose.sum() + short_setups_loose.sum()}")
