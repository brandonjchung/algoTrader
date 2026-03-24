"""
Realistic Market Data Simulator
Creates synthetic data that mimics real ES futures behavior patterns
Based on actual market characteristics and regimes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

class MarketSimulator:
    """Simulates realistic S&P 500 futures price action."""

    def __init__(self, seed=42):
        np.random.seed(seed)

    def generate_realistic_es_data(self, start_date: str, end_date: str, interval: str = "5m"):
        """
        Generate realistic ES futures data based on actual market characteristics.

        Historical ES ranges:
        - 2020: 2200-3800 (COVID crash + recovery)
        - 2021: 3700-4800 (bull market)
        - 2022: 3600-4800 (bear market, high volatility)
        - 2023: 3800-4800 (recovery)
        - 2024: 4500-5200 (continued bull)
        """
        print(f"\n{'='*70}")
        print("REALISTIC MARKET DATA SIMULATOR")
        print("Creating synthetic data based on actual ES futures characteristics")
        print(f"{'='*70}\n")

        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")
        print(f"Interval: {interval}")

        # Generate timestamps
        timestamps = self._generate_market_hours_timestamps(start_date, end_date)
        num_bars = len(timestamps)

        print(f"Generating {num_bars:,} bars with realistic market regimes...")

        # Create price series with realistic regimes
        closes = self._generate_realistic_price_series(timestamps, num_bars)

        # Generate OHLCV data
        data = self._generate_ohlcv_bars(timestamps, closes)

        # Create DataFrame
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)

        # Add realistic gaps and volatility events
        df = self._add_market_events(df, timestamps)

        print(f"\nData Summary:")
        print(f"  Total Bars: {len(df):,}")
        print(f"  Date Range: {df.index[0]} to {df.index[-1]}")
        print(f"  Price Range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")
        print(f"  Average Daily Range: ${(df['high'] - df['low']).mean():.2f}")
        print(f"  Max Single Bar Move: ${(df['high'] - df['low']).max():.2f}")

        # Calculate some statistics
        daily_returns = df['close'].resample('D').last().pct_change()
        print(f"\nRealistic Statistics:")
        print(f"  Avg Daily Return: {daily_returns.mean()*100:.3f}%")
        print(f"  Daily Volatility: {daily_returns.std()*100:.2f}%")
        print(f"  Max Daily Gain: {daily_returns.max()*100:.2f}%")
        print(f"  Max Daily Loss: {daily_returns.min()*100:.2f}%")

        # Save to file
        output_dir = "data/historical"
        os.makedirs(output_dir, exist_ok=True)

        filename = f"ES_REALISTIC_{interval}_{start_date}_to_{end_date}.csv"
        filepath = os.path.join(output_dir, filename)

        df.to_csv(filepath)

        print(f"\n✓ Saved to: {filepath}")
        print("\n" + "="*70)
        print("NOTE: This is REALISTIC SIMULATED data for testing purposes.")
        print("For live trading, use real historical data from your broker.")
        print("="*70 + "\n")

        return df, filepath

    def _generate_market_hours_timestamps(self, start_date: str, end_date: str):
        """Generate timestamps for regular trading hours (9:30 AM - 4:00 PM EST)."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        timestamps = []
        current_date = start

        while current_date <= end:
            if current_date.weekday() < 5:  # Monday-Friday
                # Regular trading hours: 9:30 AM - 4:00 PM
                for hour in range(9, 16):
                    for minute in range(0, 60, 5):
                        if hour == 9 and minute < 30:
                            continue
                        if hour == 15 and minute > 55:
                            continue

                        timestamp = current_date.replace(hour=hour, minute=minute, second=0)
                        timestamps.append(timestamp)

            current_date += timedelta(days=1)

        return timestamps

    def _generate_realistic_price_series(self, timestamps, num_bars):
        """Generate price series with realistic market regimes."""
        closes = np.zeros(num_bars)

        # Define market regimes based on actual ES history
        start_year = timestamps[0].year

        # Set starting price based on year
        if start_year <= 2020:
            closes[0] = 3200  # Pre-COVID
        elif start_year == 2021:
            closes[0] = 3750
        elif start_year == 2022:
            closes[0] = 4600
        elif start_year == 2023:
            closes[0] = 3900
        else:
            closes[0] = 4800

        # Calculate bars per day
        bars_per_day = 78  # 5-minute bars in trading day

        # Generate with realistic regime changes
        current_regime = 'normal'
        days_in_regime = 0
        regime_volatility = 0.015  # 1.5% daily vol
        regime_drift = 0.0001  # Slight upward bias

        for i in range(1, num_bars):
            # Check if we should change regimes (every 30-90 days randomly)
            if days_in_regime > np.random.randint(30, 90):
                current_regime = np.random.choice(
                    ['bull', 'bear', 'choppy', 'high_vol'],
                    p=[0.35, 0.15, 0.35, 0.15]  # Probabilities
                )
                days_in_regime = 0

                # Set regime characteristics
                if current_regime == 'bull':
                    regime_volatility = 0.012
                    regime_drift = 0.0004
                elif current_regime == 'bear':
                    regime_volatility = 0.020
                    regime_drift = -0.0003
                elif current_regime == 'choppy':
                    regime_volatility = 0.010
                    regime_drift = 0.0
                elif current_regime == 'high_vol':
                    regime_volatility = 0.025
                    regime_drift = 0.0

            # Increment day counter
            if i % bars_per_day == 0:
                days_in_regime += 1

            # Calculate bar volatility from daily volatility
            bar_volatility = regime_volatility / np.sqrt(bars_per_day)

            # Mean reversion component (pulls price toward longer-term mean)
            long_term_mean = closes[max(0, i - bars_per_day * 20):i].mean() if i > bars_per_day * 20 else closes[0]
            mean_reversion = -0.00005 * (closes[i-1] - long_term_mean) / long_term_mean

            # Random shock
            random_shock = np.random.normal(regime_drift + mean_reversion, bar_volatility)

            # Apply shock
            closes[i] = closes[i-1] * (1 + random_shock)

            # Add occasional gaps (overnight moves)
            if i % bars_per_day == 0 and np.random.random() < 0.3:  # 30% chance of gap
                gap_size = np.random.normal(0, regime_volatility * 0.3)
                closes[i] = closes[i] * (1 + gap_size)

            # Keep within realistic bounds (2000-6000 range for ES)
            closes[i] = np.clip(closes[i], 2000, 6000)

        return closes

    def _generate_ohlcv_bars(self, timestamps, closes):
        """Generate realistic OHLC bars from close prices."""
        data = []

        for i, (timestamp, close) in enumerate(zip(timestamps, closes)):
            # Calculate realistic intrabar volatility
            # Actual 5-min ES bars have range of ~0.1-0.5% of price
            bar_range_pct = np.random.uniform(0.0005, 0.003)  # 0.05% to 0.3%
            bar_range = close * bar_range_pct

            # Open is previous close plus small gap
            if i == 0:
                open_price = close
            else:
                gap = np.random.normal(0, close * 0.0002)  # Small gap
                open_price = closes[i-1] + gap

            # High and low based on range
            high_from_open = np.random.uniform(0, bar_range)
            low_from_open = -np.random.uniform(0, bar_range)

            high = max(open_price, close) + high_from_open
            low = min(open_price, close) + low_from_open

            # Ensure OHLC relationship is valid
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            # Realistic volume (ES trades 2M+ contracts/day)
            # 5-min bar: ~2500 contracts avg, with variation
            base_volume = 2500
            volume_variation = np.random.uniform(0.3, 2.0)  # 30% to 200% of base

            # Higher volume at open and close
            hour = timestamp.hour
            if hour == 9:  # Market open
                volume_variation *= 2.0
            elif hour == 15:  # Market close
                volume_variation *= 1.5

            volume = int(base_volume * volume_variation)

            data.append({
                'timestamp': timestamp,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume
            })

        return data

    def _add_market_events(self, df, timestamps):
        """Add realistic market events (spikes, crashes, etc.)."""
        # Add a few volatility spikes throughout the data
        num_events = max(1, len(df) // (252 * 78))  # ~1 event per year

        for _ in range(num_events):
            # Random event location
            event_idx = np.random.randint(78 * 20, len(df) - 78 * 20)  # Not too close to edges

            # Create volatility event (like news announcement)
            event_magnitude = np.random.uniform(0.01, 0.03)  # 1-3% move
            event_direction = np.random.choice([-1, 1])

            # Apply event over several bars
            for offset in range(10):
                if event_idx + offset < len(df):
                    current_close = df.iloc[event_idx + offset]['close']
                    shock = current_close * event_magnitude * event_direction * (1 - offset/10)

                    df.iloc[event_idx + offset, df.columns.get_loc('close')] += shock
                    df.iloc[event_idx + offset, df.columns.get_loc('high')] += max(0, shock)
                    df.iloc[event_idx + offset, df.columns.get_loc('low')] += min(0, shock)

        return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate realistic simulated market data")
    parser.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--interval", default="5m", help="Time interval")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    simulator = MarketSimulator(seed=args.seed)
    simulator.generate_realistic_es_data(args.start, args.end, args.interval)
