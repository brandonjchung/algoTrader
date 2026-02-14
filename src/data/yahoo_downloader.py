"""
Real Data Downloader from Yahoo Finance
Downloads actual historical data for MES/ES futures
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import os

def download_yahoo_data(symbol: str, start_date: str, end_date: str, interval: str = "5m"):
    """
    Download real historical data from Yahoo Finance.

    Args:
        symbol: Ticker symbol (e.g., 'ES=F' for E-mini S&P 500)
        start_date: Start date in 'YYYY-MM-DD' format
        end_date: End date in 'YYYY-MM-DD' format
        interval: Time interval ('1m', '5m', '15m', '1h', '1d')

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\nDownloading {symbol} data from Yahoo Finance...")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")
    print(f"Interval: {interval}")

    # Convert dates to Unix timestamps
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())

    # Yahoo Finance API endpoint
    url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}"

    params = {
        'period1': start_ts,
        'period2': end_ts,
        'interval': interval,
        'events': 'history',
        'includeAdjustedClose': 'true'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        print("Fetching data...")
        response = requests.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 200:
            # Parse CSV response
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            # Rename columns to match our format
            df.columns = [col.lower() for col in df.columns]
            df = df.rename(columns={'adj close': 'adj_close'})

            # Convert Date to datetime
            df['timestamp'] = pd.to_datetime(df['date'])
            df = df.drop('date', axis=1)
            df = df.set_index('timestamp')

            # Remove any null rows
            df = df.dropna()

            # Ensure correct column order
            expected_cols = ['open', 'high', 'low', 'close', 'volume']
            df = df[expected_cols]

            print(f"\nData Summary:")
            print(f"  Total Bars: {len(df)}")
            print(f"  Date Range: {df.index[0]} to {df.index[-1]}")
            print(f"  Price Range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")
            print(f"  Average Volume: {df['volume'].mean():.0f}")

            # Save to file
            output_dir = "data/historical"
            os.makedirs(output_dir, exist_ok=True)

            # Create filename
            symbol_clean = symbol.replace('=', '_')
            filename = f"{symbol_clean}_{interval}_{start_date}_to_{end_date}.csv"
            filepath = os.path.join(output_dir, filename)

            df.to_csv(filepath)
            print(f"\n✓ Saved to: {filepath}")

            return df, filepath

        else:
            print(f"✗ Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")

            # Fallback: Try alternative method using pandas directly
            print("\nTrying alternative download method...")
            return download_pandas_datareader(symbol, start_date, end_date, interval)

    except Exception as e:
        print(f"✗ Error downloading data: {e}")
        print("\nTrying alternative download method...")
        return download_pandas_datareader(symbol, start_date, end_date, interval)


def download_pandas_datareader(symbol: str, start_date: str, end_date: str, interval: str):
    """Fallback method using pandas web data reader."""
    try:
        import pandas_datareader as pdr

        print(f"Using pandas_datareader for {symbol}...")
        df = pdr.get_data_yahoo(symbol, start=start_date, end=end_date)

        # Rename columns
        df.columns = [col.lower() for col in df.columns]
        df = df.rename(columns={'adj close': 'adj_close'})

        # Keep only needed columns
        expected_cols = ['open', 'high', 'low', 'close', 'volume']
        df = df[expected_cols]

        # Save to file
        output_dir = "data/historical"
        os.makedirs(output_dir, exist_ok=True)

        symbol_clean = symbol.replace('=', '_')
        filename = f"{symbol_clean}_daily_{start_date}_to_{end_date}.csv"
        filepath = os.path.join(output_dir, filename)

        df.to_csv(filepath)
        print(f"\n✓ Saved to: {filepath}")

        return df, filepath

    except ImportError:
        print("✗ pandas_datareader not installed")
        print("\nPlease install: pip install pandas-datareader")
        return None, None
    except Exception as e:
        print(f"✗ Error with pandas_datareader: {e}")
        return None, None


def download_multiple_symbols(symbols: list, start_date: str, end_date: str, interval: str = "5m"):
    """Download data for multiple symbols."""
    results = {}

    for symbol in symbols:
        print(f"\n{'='*60}")
        data, filepath = download_yahoo_data(symbol, start_date, end_date, interval)
        results[symbol] = {'data': data, 'filepath': filepath}

        # Be nice to Yahoo servers
        time.sleep(1)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download real market data from Yahoo Finance")
    parser.add_argument("--symbol", default="ES=F", help="Ticker symbol (default: ES=F)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--interval", default="5m", help="Time interval (default: 5m)")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("YAHOO FINANCE DATA DOWNLOADER")
    print("="*60)

    download_yahoo_data(args.symbol, args.start, args.end, args.interval)

    print("\n" + "="*60)
    print("Download complete!")
    print("="*60 + "\n")
