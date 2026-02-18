"""
CSV Data Stitcher
==================
Combines multiple manually-exported TWS historical data CSVs into a single
clean file ready for backtesting.

Usage:
    # Put all your exported CSVs into one folder, then run:
    python tools/stitch_csv_data.py --input-dir "C:/path/to/exported/csvs" --symbol MES

    # Or list files explicitly:
    python tools/stitch_csv_data.py --files MES_2023Q1.csv MES_2023Q2.csv MES_2023Q3.csv

How to export from TWS:
    1. In TWS, open a chart for MES (or any contract)
    2. Right-click the chart -> Edit -> Historical Data Settings
       - Set bar size to 5 mins, date range to ~3 months
    3. Right-click chart -> Save as -> CSV
    4. Repeat for each quarterly period you want
    5. Run this script to combine them all

TWS CSV format is auto-detected. Supported column names:
    Date/Time, Open, High, Low, Close, Volume  (standard TWS export)
    timestamp, open, high, low, close, volume  (our format)
    Date, Time, Open, High, Low, Close, Volume  (split date/time columns)

Output:
    data/historical/MES_5mins_<start>_to_<end>_REAL.csv
"""

import argparse
import os
import sys
import glob

import pandas as pd


COLUMN_ALIASES = {
    # TWS standard export
    'Date/Time': 'timestamp',
    'Date': 'date_col',
    'Time': 'time_col',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Close': 'close',
    'Volume': 'volume',
    # lowercase variants
    'date/time': 'timestamp',
    'date': 'date_col',
    'time': 'time_col',
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
}


def load_csv(path):
    """Load a single TWS-exported CSV, auto-detecting format."""
    # Try reading with different skip rows (TWS sometimes has header rows)
    for skip in (0, 1, 2):
        try:
            df = pd.read_csv(path, skiprows=skip)
            if len(df.columns) >= 5:
                break
        except Exception:
            continue
    else:
        print(f"  WARNING: could not read {os.path.basename(path)}, skipping")
        return None

    # Rename columns using aliases
    df = df.rename(columns={c: COLUMN_ALIASES.get(c, c) for c in df.columns})

    # Handle split date + time columns
    if 'date_col' in df.columns and 'time_col' in df.columns:
        df['timestamp'] = pd.to_datetime(
            df['date_col'].astype(str) + ' ' + df['time_col'].astype(str),
            errors='coerce'
        )
        df = df.drop(columns=['date_col', 'time_col'])
    elif 'date_col' in df.columns:
        df = df.rename(columns={'date_col': 'timestamp'})

    if 'timestamp' not in df.columns:
        print(f"  WARNING: no timestamp column in {os.path.basename(path)}, skipping")
        print(f"    Columns found: {list(df.columns)}")
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=False, errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # Strip timezone
    if hasattr(df['timestamp'].dt, 'tz') and df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)

    required = ['open', 'high', 'low', 'close']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  WARNING: missing columns {missing} in {os.path.basename(path)}, skipping")
        return None

    if 'volume' not in df.columns:
        df['volume'] = 0

    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df = df[pd.to_numeric(df['close'], errors='coerce').notna()]
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def main():
    parser = argparse.ArgumentParser(description='Stitch multiple TWS CSV exports into one file')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-dir', help='Directory containing CSV files to stitch')
    group.add_argument('--files', nargs='+', help='Explicit list of CSV files')
    parser.add_argument('--symbol', default='MES', help='Symbol name for output filename')
    parser.add_argument('--output-dir', default='data/historical',
                        help='Output directory (default: data/historical)')
    args = parser.parse_args()

    # Collect files
    if args.input_dir:
        pattern = os.path.join(args.input_dir, '*.csv')
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"ERROR: no CSV files found in {args.input_dir}")
            sys.exit(1)
    else:
        files = args.files

    print(f"\nStitching {len(files)} CSV file(s)...")

    all_frames = []
    for path in files:
        name = os.path.basename(path)
        df = load_csv(path)
        if df is not None and len(df) > 0:
            print(f"  {name}: {len(df):,} bars  "
                  f"({df['timestamp'].min().date()} to {df['timestamp'].max().date()})")
            all_frames.append(df)
        else:
            print(f"  {name}: skipped")

    if not all_frames:
        print("\nERROR: no valid data loaded.")
        sys.exit(1)

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=['timestamp'])
    combined = combined.sort_values('timestamp').reset_index(drop=True)
    combined = combined.dropna(subset=['open', 'high', 'low', 'close'])

    actual_start = combined['timestamp'].min().strftime('%Y-%m-%d')
    actual_end = combined['timestamp'].max().strftime('%Y-%m-%d')
    days = (combined['timestamp'].max() - combined['timestamp'].min()).days

    os.makedirs(args.output_dir, exist_ok=True)
    filename = f"{args.symbol}_5mins_{actual_start}_to_{actual_end}_REAL.csv"
    out_path = os.path.join(args.output_dir, filename)
    combined.set_index('timestamp').to_csv(out_path)

    print(f"\nOutput : {out_path}")
    print(f"Bars   : {len(combined):,}")
    print(f"Range  : {actual_start} to {actual_end}  ({days} days)")
    print(f"Avg/day: {len(combined) / max(days, 1) * 7:.0f} bars/calendar-day")
    print(f"\nNext:")
    print(f"  python tools/calibrate_filters.py {filename}")
    print(f"  python src/backtest/run_backtest.py --config <config> --data-file {filename}")


if __name__ == '__main__':
    main()
