"""
Data Downloader

Downloads historical futures data for backtesting.
Uses yfinance for ES data as a proxy for MES.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf
import os
import argparse


def download_es_data(start_date: str, end_date: str, interval: str = '5m') -> pd.DataFrame:
    """
    Download E-mini S&P 500 data as proxy for MES.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Bar interval (1m, 5m, 15m, 1h, 1d)
        
    Returns:
        DataFrame with OHLCV data
    """
    print(f"Downloading ES data from {start_date} to {end_date} ({interval} bars)...")
    
    symbol = "ES=F"
    
    try:
        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=True
        )
        
        if data.empty:
            print(f"ERROR: No data returned for {symbol}")
            return None
        
        # Clean up column names
        data.columns = [col.lower() for col in data.columns]
        
        # Remove any rows with NaN
        initial_len = len(data)
        data = data.dropna()
        removed = initial_len - len(data)
        
        if removed > 0:
            print(f"  Removed {removed} bars with missing data")
        
        print(f"\nData Quality Check:")
        print(f"  Total bars: {len(data)}")
        print(f"  Date range: {data.index[0]} to {data.index[-1]}")
        print(f"  Price range: ${data['low'].min():.2f} to ${data['high'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"ERROR downloading data: {e}")
        return None


def save_data(data: pd.DataFrame, filename: str):
    """Save data to CSV file."""
    output_dir = 'data/historical'
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    data.to_csv(filepath)
    
    print(f"\nData saved to: {filepath}")
    print(f"File size: {os.path.getsize(filepath) / 1024:.2f} KB")


def load_data(filename: str) -> pd.DataFrame:
    """Load data from CSV file."""
    filepath = os.path.join('data/historical', filename)
    
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return None
    
    data = pd.read_csv(filepath, index_col=0, parse_dates=True)
    print(f"Loaded {len(data)} bars from {filepath}")
    
    return data


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Download historical data for backtesting')
    parser.add_argument('--symbol', default='MES', help='Symbol to download (MES or ES)')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--interval', default='5m', help='Bar interval (1m, 5m, 15m, 1h, 1d)')
    parser.add_argument('--output', help='Output filename (auto-generated if not provided)')
    
    args = parser.parse_args()
    
    # Download data
    data = download_es_data(args.start, args.end, args.interval)
    
    if data is None:
        print("Failed to get data")
        return
    
    # Generate filename if not provided
    if args.output:
        filename = args.output
    else:
        filename = f"MES_{args.interval}_{args.start}_to_{args.end}.csv"
    
    # Save data
    save_data(data, filename)
    
    print("\nData download complete!")
    print(f"You can now run backtests with this data.")


if __name__ == "__main__":
    main()
