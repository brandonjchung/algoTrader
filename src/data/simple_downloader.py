"""
Simple Data Downloader - Alternative to yfinance
Downloads historical data for backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def download_sample_data(start_date: str, end_date: str, interval: str = "5m"):
    """
    Generate realistic sample data for testing purposes.
    In production, replace this with real data from a broker or data provider.
    """
    print(f"\nGenerating sample MES futures data...")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    print(f"Interval: {interval}")

    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Generate timestamps (5-minute intervals during market hours)
    # Market hours: 9:30 AM - 4:00 PM EST (6.5 hours = 390 minutes = 78 bars per day)
    timestamps = []
    current_date = start

    while current_date <= end:
        # Skip weekends
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            # Generate bars from 9:30 AM to 4:00 PM
            for hour in range(9, 16):
                for minute in range(0, 60, 5):
                    if hour == 9 and minute < 30:
                        continue  # Skip before 9:30 AM
                    if hour == 15 and minute > 55:
                        continue  # Skip after 3:55 PM

                    timestamp = current_date.replace(hour=hour, minute=minute, second=0)
                    timestamps.append(timestamp)

        current_date += timedelta(days=1)

    num_bars = len(timestamps)
    print(f"Generating {num_bars} bars...")

    # Generate realistic S&P 500 futures price action
    # Base price around 4500 with realistic volatility
    base_price = 4500.0
    daily_volatility = 0.015  # 1.5% daily volatility
    bar_volatility = daily_volatility / np.sqrt(78)  # 78 bars per day (5-min bars)

    # Generate random walk with mean reversion
    np.random.seed(42)  # For reproducibility

    # Create price series with random walk but bounded
    closes = np.zeros(num_bars)
    closes[0] = base_price

    for i in range(1, num_bars):
        # Mean reversion tendency - pull price back toward base
        mean_reversion = -0.0001 * (closes[i-1] - base_price) / base_price
        random_shock = np.random.normal(mean_reversion, bar_volatility)
        closes[i] = closes[i-1] * (1 + random_shock)

        # Ensure prices stay in realistic range (4000 to 5000)
        closes[i] = np.clip(closes[i], 4000, 5000)

    # Generate OHLC data
    data = []
    for i, (timestamp, close) in enumerate(zip(timestamps, closes)):
        # Generate realistic OHLC bars
        atr = close * 0.002  # Average True Range ~0.2%

        # High and Low relative to close
        high = close + np.random.uniform(0, atr)
        low = close - np.random.uniform(0, atr)

        # Open is previous close (or close to it)
        if i == 0:
            open_price = close
        else:
            open_price = closes[i-1] + np.random.uniform(-atr/2, atr/2)

        # Ensure OHLC relationship is valid
        high = max(high, open_price, close)
        low = min(low, open_price, close)

        # Volume (random but realistic)
        volume = np.random.randint(1000, 5000)

        data.append({
            'timestamp': timestamp,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume
        })

    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)

    # Save to file
    output_dir = "data/historical"
    os.makedirs(output_dir, exist_ok=True)

    filename = f"MES_5m_{start_date}_to_{end_date}.csv"
    filepath = os.path.join(output_dir, filename)

    df.to_csv(filepath)

    print(f"\nData Summary:")
    print(f"  Total Bars: {len(df)}")
    print(f"  Date Range: {df.index[0]} to {df.index[-1]}")
    print(f"  Price Range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")
    print(f"  Saved to: {filepath}")

    print("\n⚠️  NOTE: This is SAMPLE DATA for testing purposes only!")
    print("For live trading, use real historical data from your broker or a data provider.")

    return filepath

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download MES futures data")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--interval", default="5m", help="Time interval (default: 5m)")

    args = parser.parse_args()

    download_sample_data(args.start, args.end, args.interval)
