"""
Market Condition Analyzer for Real IB Data

Analyzes the actual market data to understand:
- Volatility regimes
- Trending vs ranging periods
- Volume patterns
- Best trading hours
- Market characteristics

This helps optimize strategy for current conditions.
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime

def analyze_market_conditions(data_file):
    """Analyze market conditions in real IB data"""

    print("\n" + "="*60)
    print("MARKET CONDITION ANALYSIS")
    print("="*60 + "\n")

    # Load data
    print(f"Loading data from {data_file}...")
    df = pd.read_csv(data_file, index_col=0, parse_dates=True)

    # Remove timezone if present
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    print(f"Loaded {len(df)} bars")
    print(f"Date Range: {df.index[0]} to {df.index[-1]}")
    print(f"Total Days: {(df.index[-1] - df.index[0]).days}\n")

    # Calculate technical indicators
    print("Calculating indicators...")

    # ATR (14 periods)
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_close'] = abs(df['low'] - df['close'].shift(1))
    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr'] = df['true_range'].rolling(window=14).mean()

    # Volatility (std of returns)
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=20).std() * 100

    # Trend strength (ADX concept - simplified)
    df['price_change'] = df['close'].diff()
    df['trending'] = abs(df['price_change'].rolling(window=14).mean()) / df['atr']

    # Volume analysis
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']

    # Hour of day
    df['hour'] = df.index.hour

    # Remove NaN rows
    df = df.dropna()

    print("\n" + "="*60)
    print("VOLATILITY ANALYSIS")
    print("="*60)
    print(f"Average ATR: {df['atr'].mean():.2f} points")
    print(f"Median ATR: {df['atr'].median():.2f} points")
    print(f"ATR Range: {df['atr'].min():.2f} - {df['atr'].max():.2f} points")
    print(f"Average Daily Volatility: {df['volatility'].mean():.2f}%")

    # Volatility regimes
    low_vol = df['atr'] < df['atr'].quantile(0.33)
    med_vol = (df['atr'] >= df['atr'].quantile(0.33)) & (df['atr'] < df['atr'].quantile(0.67))
    high_vol = df['atr'] >= df['atr'].quantile(0.67)

    print(f"\nVolatility Regimes:")
    print(f"  Low Vol (<{df['atr'].quantile(0.33):.2f}): {low_vol.sum()} bars ({low_vol.sum()/len(df)*100:.1f}%)")
    print(f"  Med Vol: {med_vol.sum()} bars ({med_vol.sum()/len(df)*100:.1f}%)")
    print(f"  High Vol (>{df['atr'].quantile(0.67):.2f}): {high_vol.sum()} bars ({high_vol.sum()/len(df)*100:.1f}%)")

    print("\n" + "="*60)
    print("MARKET TREND ANALYSIS")
    print("="*60)

    # Overall trend
    start_price = df['close'].iloc[0]
    end_price = df['close'].iloc[-1]
    total_return = ((end_price - start_price) / start_price) * 100

    print(f"Overall Market Move: {total_return:+.2f}%")
    print(f"Start Price: ${start_price:.2f}")
    print(f"End Price: ${end_price:.2f}")

    # Trending vs ranging
    trending_pct = (df['trending'] > 0.5).sum() / len(df) * 100
    print(f"\nTrending Market: {trending_pct:.1f}% of time")
    print(f"Ranging Market: {100-trending_pct:.1f}% of time")

    print("\n" + "="*60)
    print("HOURLY ANALYSIS (Best Trading Hours)")
    print("="*60)

    hourly = df.groupby('hour').agg({
        'returns': ['mean', 'std', 'count'],
        'volume': 'mean',
        'atr': 'mean',
        'volatility': 'mean'
    }).round(4)

    print("\nAverage Returns by Hour:")
    for hour in sorted(df['hour'].unique()):
        hour_data = df[df['hour'] == hour]
        avg_return = hour_data['returns'].mean() * 100
        volatility = hour_data['volatility'].mean()
        count = len(hour_data)
        print(f"  {hour:02d}:00 - Avg Return: {avg_return:+.4f}%, Vol: {volatility:.2f}%, Bars: {count}")

    print("\n" + "="*60)
    print("VOLUME ANALYSIS")
    print("="*60)
    print(f"Average Volume: {df['volume'].mean():,.0f}")
    print(f"Median Volume: {df['volume'].median():,.0f}")
    print(f"Volume Range: {df['volume'].min():,.0f} - {df['volume'].max():,.0f}")

    # High volume bars
    high_volume = df['volume_ratio'] > 1.5
    print(f"\nHigh Volume Bars (>1.5x avg): {high_volume.sum()} ({high_volume.sum()/len(df)*100:.1f}%)")
    print(f"Average Return on High Volume: {df[high_volume]['returns'].mean()*100:+.4f}%")

    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)

    # Generate recommendations
    recommendations = []

    if df['atr'].mean() > 5:
        recommendations.append("✅ ATR is high - Good for breakout strategies")
    else:
        recommendations.append("⚠️  ATR is low - Consider mean reversion instead")

    if trending_pct > 60:
        recommendations.append("✅ Market is trending - Breakouts should work well")
    else:
        recommendations.append("⚠️  Market is ranging - Tighten stops, use mean reversion")

    if total_return > 10:
        recommendations.append("📈 Strong bull market - Favor LONG positions")
    elif total_return < -10:
        recommendations.append("📉 Bear market - Favor SHORT or mean reversion")
    else:
        recommendations.append("➡️  Sideways market - Trade both directions")

    # Find best trading hours
    hourly_returns = df.groupby('hour')['returns'].mean()
    best_hours = hourly_returns.nlargest(3).index.tolist()
    worst_hours = hourly_returns.nsmallest(3).index.tolist()

    recommendations.append(f"🕐 Best hours to trade: {', '.join([f'{h:02d}:00' for h in best_hours])}")
    recommendations.append(f"⏰ Avoid hours: {', '.join([f'{h:02d}:00' for h in worst_hours])}")

    for rec in recommendations:
        print(f"  {rec}")

    print("\n" + "="*60 + "\n")

    return df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python market_analyzer.py <data_file>")
        print("Example: python market_analyzer.py data/historical/MES_5mins_2024-12-20_to_2026-02-13_REAL.csv")
        sys.exit(1)

    data_file = sys.argv[1]
    analyze_market_conditions(data_file)
