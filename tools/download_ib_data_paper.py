"""
IB Historical Data Downloader (Paper Account Optimized)
========================================================
Downloads maximum available history from IB paper trading account.
Starts from most recent contracts and works backwards until blocked.

Usage:
    python tools/download_ib_data_paper.py --symbol MES --port 7497
"""

import argparse
import time
import os
import sys
from datetime import datetime, timedelta

# Python 3.14+ compatibility
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import pandas as pd

QUARTER_MONTHS = [3, 6, 9, 12]


def get_recent_contracts(symbol, months_back=18):
    """Get quarterly contracts from now backwards."""
    now = datetime.now()
    start = now - timedelta(days=months_back * 30)

    contracts = []
    for year in range(start.year, now.year + 2):
        for month in QUARTER_MONTHS:
            dt = datetime(year, month, 15)
            if start <= dt <= now + timedelta(days=180):
                contracts.append((year, month))

    return sorted(contracts, reverse=True)  # newest first


def make_contract(symbol, year, month, multiplier, exchange):
    from ib_insync import Future
    c = Future(
        symbol=symbol,
        exchange=exchange,
        currency='USD',
        multiplier=multiplier,
        lastTradeDateOrContractMonth=f"{year}{month:02d}",
    )
    c.includeExpired = True
    return c


def download_contract_history(ib, symbol, year, month, multiplier):
    from ib_insync import util

    # Try CME first, then GLOBEX
    contract = None
    for exchange in ('CME', 'GLOBEX'):
        c = make_contract(symbol, year, month, multiplier, exchange)
        try:
            qualified = ib.qualifyContracts(c)
            if qualified:
                contract = c
                break
        except Exception:
            pass

    if contract is None:
        contract = make_contract(symbol, year, month, multiplier, 'CME')

    # Try to get up to 6 months of data per contract
    all_frames = []
    for duration in ['180 D', '90 D', '60 D', '30 D']:
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',  # empty = most recent
                durationStr=duration,
                barSizeSetting='5 mins',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1,
                keepUpToDate=False,
            )
            if bars:
                df = util.df(bars)
                df = df.rename(columns={'date': 'timestamp'})
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                all_frames.append(df)
                break  # got data, stop trying
        except Exception:
            continue
        time.sleep(0.5)

    if not all_frames:
        return None

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)
    return combined


def main():
    parser = argparse.ArgumentParser(description='Download max available IB data (paper account)')
    parser.add_argument('--symbol', default='MES', help='Futures symbol')
    parser.add_argument('--port', type=int, default=7497, help='TWS port (7497=paper)')
    parser.add_argument('--multiplier', default='5', help='Contract multiplier')
    args = parser.parse_args()

    try:
        from ib_insync import IB
    except ImportError:
        print("ERROR: ib_insync not installed. Run: pip install ib_insync")
        sys.exit(1)

    ib = IB()
    print(f"\nConnecting to TWS at 127.0.0.1:{args.port}...")
    try:
        ib.connect('127.0.0.1', args.port, clientId=10)
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        print("\nMake sure TWS is open with API enabled:")
        print("  File → Global Configuration → API → Settings")
        print("  → Check 'Enable ActiveX and Socket Clients'")
        sys.exit(1)

    print("Connected. Downloading from most recent contracts backwards...\n")

    contracts = get_recent_contracts(args.symbol, months_back=18)
    print(f"Trying {len(contracts)} recent quarterly contracts:\n")

    all_frames = []
    successful = 0
    failed_consecutive = 0

    for i, (year, month) in enumerate(contracts, 1):
        month_name = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month]
        print(f"[{i}/{len(contracts)}] {args.symbol} {month_name} {year}...", end=' ', flush=True)

        df = download_contract_history(ib, args.symbol, year, month, args.multiplier)

        if df is not None and len(df) > 0:
            all_frames.append(df)
            successful += 1
            failed_consecutive = 0
            print(f"✓ {len(df):,} bars  ({df['timestamp'].min().date()} to {df['timestamp'].max().date()})")
        else:
            failed_consecutive += 1
            print("✗ no data")
            if failed_consecutive >= 3:
                print(f"\n3 consecutive failures - stopped (paper account limit reached)")
                break

        time.sleep(1)

    ib.disconnect()

    if not all_frames:
        print("\nERROR: No data downloaded.")
        print("Paper accounts typically can only access last 6-12 months.")
        sys.exit(1)

    print(f"\n✓ Successfully downloaded {successful} contracts")
    print(f"Assembling data...")

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)

    if hasattr(combined['timestamp'].dt, 'tz') and combined['timestamp'].dt.tz is not None:
        combined['timestamp'] = combined['timestamp'].dt.tz_localize(None)

    actual_start = combined['timestamp'].min().strftime('%Y-%m-%d')
    actual_end = combined['timestamp'].max().strftime('%Y-%m-%d')
    days = (combined['timestamp'].max() - combined['timestamp'].min()).days

    os.makedirs('data/historical', exist_ok=True)
    filename = f"{args.symbol}_5mins_{actual_start}_to_{actual_end}_REAL.csv"
    out_path = os.path.join('data/historical', filename)
    combined.set_index('timestamp').to_csv(out_path)

    print(f"\n{'='*70}")
    print(f"SUCCESS: Saved {len(combined):,} bars → data/historical/{filename}")
    print(f"{'='*70}")
    print(f"  Date range : {actual_start} to {actual_end}  ({days} days)")
    print(f"  Bars/day   : {len(combined) / max(days, 1):.0f} avg")
    print(f"\nNext steps:")
    print(f"  python tools/calibrate_filters.py {filename}")
    print(f"  python src/backtest/run_backtest.py --config <config> --data-file {filename}")


if __name__ == '__main__':
    main()
