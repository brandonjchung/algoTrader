"""
IB Historical Data Downloader
==============================
Downloads 5-minute OHLCV bars for MES (or any symbol) from Interactive Brokers
TWS/Gateway and saves to data/historical/.

IB does NOT allow endDateTime with ContFuture. Instead we iterate through
individual quarterly expired contracts (H/M/U/Z) and stitch them together.

Requirements:
    pip install ib_insync

Setup:
    1. Open TWS or IB Gateway
    2. Enable API: File -> Global Configuration -> API -> Settings
       - Check "Enable ActiveX and Socket Clients"
       - Port: 7497 (TWS paper), 7496 (TWS live), 4002 (Gateway paper), 4001 (Gateway live)
    3. Run this script

Usage:
    python tools/download_ib_data.py --symbol MES --years 3
    python tools/download_ib_data.py --symbol MES --years 3 --port 4002
    python tools/download_ib_data.py --symbol ES  --years 3

Output:
    data/historical/MES_5mins_<start>_to_<end>_REAL.csv
"""

import argparse
import time
import os
import sys
from datetime import datetime, timedelta

import pandas as pd


# MES/ES quarterly expiry months: H=Mar, M=Jun, U=Sep, Z=Dec
# Approximate last trading day: 3rd Friday of expiry month
QUARTER_MONTHS = [3, 6, 9, 12]


def get_quarterly_contracts(symbol, years_back):
    """
    Return list of (year, month) for quarterly futures going back N years,
    oldest first. Each tuple represents one front-month period to download.
    """
    now = datetime.now()
    start = now - timedelta(days=int(years_back * 365) + 90)

    contracts = []
    for year in range(start.year, now.year + 1):
        for month in QUARTER_MONTHS:
            dt = datetime(year, month, 1)
            if start <= dt <= now + timedelta(days=90):
                contracts.append((year, month))

    return sorted(contracts)


def approx_expiry(year, month):
    """Approximate the 3rd Friday of the expiry month (close enough for endDateTime)."""
    # Find first Friday of the month
    first = datetime(year, month, 1)
    days_to_friday = (4 - first.weekday()) % 7  # 4 = Friday
    first_friday = first + timedelta(days=days_to_friday)
    third_friday = first_friday + timedelta(weeks=2)
    return third_friday


def download_contract_history(ib, symbol, year, month, chunk_days=5):
    """
    Download all 5-min bars for one quarterly contract.
    Walks backwards from expiry in weekly chunks.
    Returns DataFrame or None.
    """
    from ib_insync import Future, util

    contract_month = f"{year}{month:02d}"
    contract = Future(
        symbol=symbol,
        exchange='CME',
        currency='USD',
        lastTradeDateOrContractMonth=contract_month,
        includeExpired=True,
    )

    # Qualify the contract to get full details
    try:
        ib.qualifyContracts(contract)
    except Exception:
        pass  # will try anyway

    # Download period: 3 months before expiry (the front-month liquid period)
    expiry = approx_expiry(year, month)
    period_start = expiry - timedelta(days=95)  # ~3 months back
    now = datetime.now()
    if expiry > now:
        expiry = now  # don't request future dates

    all_frames = []
    current_end = expiry

    while current_end > period_start:
        end_str = current_end.strftime('%Y%m%d %H:%M:%S') + ' US/Eastern'
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=end_str,
                durationStr=f'{chunk_days} D',
                barSizeSetting='5 mins',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1,
                keepUpToDate=False,
            )
        except Exception as e:
            print(f"\n    chunk error: {e}")
            bars = []

        if bars:
            df = util.df(bars)
            df = df.rename(columns={'date': 'timestamp'})
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            all_frames.append(df)

        current_end -= timedelta(days=chunk_days)
        time.sleep(0.4)  # respect IB pacing limit

    if not all_frames:
        return None

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)
    return combined


def main():
    parser = argparse.ArgumentParser(description='Download IB historical data')
    parser.add_argument('--symbol', default='MES', help='Futures symbol (default: MES)')
    parser.add_argument('--years', type=float, default=3.0,
                        help='Years of history to download (default: 3)')
    parser.add_argument('--host', default='127.0.0.1', help='TWS/Gateway host')
    parser.add_argument('--port', type=int, default=7497,
                        help='TWS/Gateway port (7497=TWS paper, 7496=TWS live, '
                             '4002=Gateway paper, 4001=Gateway live)')
    parser.add_argument('--client-id', type=int, default=10,
                        help='IB API client ID (default: 10)')
    args = parser.parse_args()

    try:
        from ib_insync import IB
    except ImportError:
        print("ERROR: ib_insync not installed.")
        print("  Run: pip install ib_insync")
        sys.exit(1)

    ib = IB()
    print(f"\nConnecting to TWS/Gateway at {args.host}:{args.port} (clientId={args.client_id})...")
    try:
        ib.connect(args.host, args.port, clientId=args.client_id)
    except Exception as e:
        print(f"\nERROR: Could not connect: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure TWS or IB Gateway is open and logged in")
        print("  2. Enable API: File -> Global Configuration -> API -> Settings")
        print("     -> Check 'Enable ActiveX and Socket Clients'")
        print(f"  3. Confirm port {args.port} matches your TWS/Gateway setting")
        print("  4. TWS paper trading: --port 7497")
        print("  5. IB Gateway paper: --port 4002")
        sys.exit(1)

    print(f"Connected. Building {args.years}-year history from quarterly contracts...\n")

    quarterly = get_quarterly_contracts(args.symbol, args.years)
    print(f"Contracts to download: {len(quarterly)}")
    for y, m in quarterly:
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m]
        print(f"  {args.symbol} {month_name} {y}  ({y}{m:02d})")
    print()

    all_frames = []
    for i, (year, month) in enumerate(quarterly, 1):
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month]
        print(f"[{i}/{len(quarterly)}] Downloading {args.symbol} {month_name} {year}...", end=' ', flush=True)

        df = download_contract_history(ib, args.symbol, year, month)

        if df is not None and len(df) > 0:
            all_frames.append(df)
            print(f"{len(df):,} bars")
        else:
            print("no data (contract may be expired/unavailable)")

        time.sleep(1)  # pause between contracts

    ib.disconnect()

    if not all_frames:
        print("\nERROR: No data downloaded.")
        sys.exit(1)

    print(f"\nAssembling {len(all_frames)} contracts...")
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)

    # Strip timezone if present
    if hasattr(combined['timestamp'].dt, 'tz') and combined['timestamp'].dt.tz is not None:
        combined['timestamp'] = combined['timestamp'].dt.tz_localize(None)

    # Trim to requested range
    start_dt = datetime.now() - timedelta(days=int(args.years * 365))
    combined = combined[combined['timestamp'] >= pd.Timestamp(start_dt)]

    actual_start = combined['timestamp'].min().strftime('%Y-%m-%d')
    actual_end = combined['timestamp'].max().strftime('%Y-%m-%d')

    os.makedirs('data/historical', exist_ok=True)
    filename = f"{args.symbol}_5mins_{actual_start}_to_{actual_end}_REAL.csv"
    out_path = os.path.join('data/historical', filename)
    combined.set_index('timestamp').to_csv(out_path)

    print(f"\nSaved {len(combined):,} bars -> {out_path}")
    print(f"  Range      : {actual_start} to {actual_end}")
    print(f"  Bars/day   : {len(combined) / (args.years * 252):.0f} avg")
    print(f"\nNext steps:")
    print(f"  python tools/calibrate_filters.py {filename}")
    print(f"  python src/backtest/run_backtest.py --config <config> --data-file {filename}")


if __name__ == '__main__':
    main()
