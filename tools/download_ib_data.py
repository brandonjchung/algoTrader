"""
IB Historical Data Downloader
==============================
Downloads 5-minute OHLCV bars for MES (or any symbol) from Interactive Brokers
TWS/Gateway and saves to data/historical/.

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
    python tools/download_ib_data.py --symbol ES  --years 3 --multiplier 50

Output:
    data/historical/MES_5mins_<start>_to_<end>_REAL.csv
"""

import argparse
import time
import os
import sys
from datetime import datetime, timedelta

import pandas as pd


def get_contract(ib, symbol, multiplier):
    from ib_insync import Future, ContFuture
    # Use continuous future for multi-year history (rolls automatically)
    contract = ContFuture(symbol=symbol, exchange='CME', currency='USD')
    contract.includeExpired = True
    details = ib.reqContractDetails(contract)
    if not details:
        print(f"  Warning: no contract details found for {symbol}, trying Future directly")
        contract = Future(symbol=symbol, exchange='CME', currency='USD')
    return contract


def download_chunk(ib, contract, end_dt, duration='1 W'):
    """Download one chunk of 5-min bars ending at end_dt."""
    from ib_insync import util
    end_str = end_dt.strftime('%Y%m%d %H:%M:%S') + ' US/Eastern'
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=end_str,
        durationStr=duration,
        barSizeSetting='5 mins',
        whatToShow='TRADES',
        useRTH=False,           # include extended hours
        formatDate=1,
        keepUpToDate=False,
    )
    if not bars:
        return None
    df = util.df(bars)
    df = df.rename(columns={'date': 'timestamp', 'open': 'open', 'high': 'high',
                             'low': 'low', 'close': 'close', 'volume': 'volume'})
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


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
    parser.add_argument('--multiplier', default='5',
                        help='Contract multiplier (default: 5 for MES, 50 for ES)')
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
        print("  4. For TWS paper trading use --port 7497")
        print("  5. For IB Gateway paper trading use --port 4002")
        sys.exit(1)

    print(f"Connected. Downloading {args.years} years of {args.symbol} 5-min bars...")

    contract = get_contract(ib, args.symbol, args.multiplier)

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(args.years * 365))
    total_days = (end_dt - start_dt).days
    chunk_days = 5  # IB allows max 1 week per request for 5-min bars

    all_frames = []
    current_end = end_dt
    chunks_done = 0
    total_chunks = (total_days // chunk_days) + 1

    print(f"Downloading {start_dt.date()} to {end_dt.date()} in {total_chunks} weekly chunks...\n")

    while current_end > start_dt:
        chunks_done += 1
        pct = int((chunks_done / total_chunks) * 100)
        print(f"  [{pct:3d}%] Chunk {chunks_done}/{total_chunks}: ending {current_end.strftime('%Y-%m-%d')}", end='\r')

        try:
            df = download_chunk(ib, contract, current_end, duration='1 W')
        except Exception as e:
            print(f"\n  Warning: chunk failed ({e}), skipping...")
            current_end -= timedelta(days=chunk_days)
            time.sleep(2)
            continue

        if df is not None and len(df) > 0:
            all_frames.append(df)

        current_end -= timedelta(days=chunk_days)
        time.sleep(0.5)  # respect IB rate limits (max ~50 requests/10s)

    ib.disconnect()
    print(f"\n\nDownload complete. Assembling {len(all_frames)} chunks...")

    if not all_frames:
        print("ERROR: No data downloaded.")
        sys.exit(1)

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)
    combined['timestamp'] = combined['timestamp'].dt.tz_localize(None)

    # Trim to requested range
    combined = combined[combined['timestamp'] >= pd.Timestamp(start_dt)]

    actual_start = combined['timestamp'].min().strftime('%Y-%m-%d')
    actual_end = combined['timestamp'].max().strftime('%Y-%m-%d')

    os.makedirs('data/historical', exist_ok=True)
    filename = f"{args.symbol}_5mins_{actual_start}_to_{actual_end}_REAL.csv"
    out_path = os.path.join('data/historical', filename)

    combined.set_index('timestamp').to_csv(out_path)

    print(f"\nSaved {len(combined):,} bars to {out_path}")
    print(f"  Date range : {actual_start} to {actual_end}")
    print(f"  Bars/day   : {len(combined) / (args.years * 252):.0f} avg")
    print(f"\nRun your backtest with:")
    print(f"  python src/backtest/run_backtest.py --config <config> --data-file {filename}")


if __name__ == '__main__':
    main()
