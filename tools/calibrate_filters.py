"""
Filter Calibration Tool

Measures actual indicator distributions from real MES data
so we can set meaningful thresholds for signal quality filters.

Usage:
    python tools/calibrate_filters.py MES_5mins_2025-02-14_to_2026-02-13_REAL.csv
"""

import pandas as pd
import numpy as np
import sys


def calibrate(data_file):
    print(f"\nLoading {data_file}...")
    df = pd.read_csv(f"data/historical/{data_file}")
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.set_index('timestamp')

    # Calculate same indicators as the strategy
    bb_period = 20
    bb_std_mult = 2.0
    atr_period = 14

    df['bb_middle'] = df['close'].rolling(bb_period).mean()
    bb_std = df['close'].rolling(bb_period).std()
    df['bb_upper'] = df['bb_middle'] + bb_std_mult * bb_std
    df['bb_lower'] = df['bb_middle'] - bb_std_mult * bb_std
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100  # as %

    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(atr_period).mean()

    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']

    # Filter to trading hours and ATR filter range (same as baseline strategy)
    allowed_hours = [13, 16, 21]
    df_filtered = df[df.index.hour.isin(allowed_hours)]
    df_filtered = df_filtered[(df_filtered['atr'] <= 5.0) & (df_filtered['atr'] >= 1.5)]
    df_filtered = df_filtered.dropna()

    print(f"\nBars at allowed hours with ATR filter applied: {len(df_filtered)}")

    print("\n" + "=" * 50)
    print("BB WIDTH (% of price) - at signal-eligible bars")
    print("=" * 50)
    bw = df_filtered['bb_width']
    for pct in [10, 25, 50, 60, 70, 75, 80, 90]:
        print(f"  {pct}th percentile: {bw.quantile(pct/100):.3f}%")
    print(f"  Mean:              {bw.mean():.3f}%")
    print(f"  Std:               {bw.std():.3f}%")
    print(f"\n  --> Suggested min_bb_width_pct thresholds:")
    print(f"      0.50% = top ~{100 - int(bw.lt(0.50).mean()*100)}% most extended (aggressive)")
    print(f"      0.60% = top ~{100 - int(bw.lt(0.60).mean()*100)}% most extended")
    print(f"      0.70% = top ~{100 - int(bw.lt(0.70).mean()*100)}% most extended (recommended)")
    print(f"      0.80% = top ~{100 - int(bw.lt(0.80).mean()*100)}% most extended (conservative)")

    print("\n" + "=" * 50)
    print("VOLUME RATIO - at signal-eligible bars")
    print("=" * 50)
    vr = df_filtered['volume_ratio']
    for pct in [10, 25, 50, 75, 80, 90]:
        print(f"  {pct}th percentile: {vr.quantile(pct/100):.3f}x")
    print(f"  Mean:              {vr.mean():.3f}x")
    print(f"\n  --> Suggested thresholds:")
    print(f"      LOW volume (<0.8x):  {int(vr.lt(0.8).mean()*100)}% of bars qualify")
    print(f"      LOW volume (<0.9x):  {int(vr.lt(0.9).mean()*100)}% of bars qualify")
    print(f"      HIGH volume (>1.2x): {int(vr.gt(1.2).mean()*100)}% of bars qualify (was tested)")
    print(f"      HIGH volume (>1.5x): {int(vr.gt(1.5).mean()*100)}% of bars qualify")

    print("\n" + "=" * 50)
    print("ATR DISTRIBUTION - at signal-eligible bars")
    print("=" * 50)
    at = df_filtered['atr']
    for pct in [10, 25, 50, 75, 90]:
        print(f"  {pct}th percentile: {at.quantile(pct/100):.2f}")
    print(f"  Mean:              {at.mean():.2f}")

    # Also show what % of all bars pass the ATR filter
    df_all = df.dropna(subset=['atr'])
    df_hours = df_all[df_all.index.hour.isin(allowed_hours)]
    pct_pass = (df_hours['atr'].between(1.5, 5.0)).mean() * 100
    print(f"\n  ATR filter (1.5-5.0) passes {pct_pass:.1f}% of eligible-hour bars")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python tools/calibrate_filters.py <data_file>")
        sys.exit(1)
    calibrate(sys.argv[1])
