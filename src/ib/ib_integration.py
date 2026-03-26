"""
Interactive Brokers Integration Module
======================================

This module handles:
1. Connection to IB TWS/Gateway
2. Downloading historical data (for backtesting)
3. Live market data (for paper/live trading)
4. Account management
5. Order execution (when ready)

Requirements:
- IB account (paper or live)
- TWS or IB Gateway running
- API enabled in TWS settings
"""

from ib_insync import IB, util, Contract, BarDataList
import pandas as pd
from datetime import datetime, timedelta
import time
import os


class IBConnection:
    """Manage Interactive Brokers connection and data."""

    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IB connection.

        Args:
            host: IB Gateway/TWS host (default: localhost)
            port: 7497 for paper trading, 7496 for live
            client_id: Unique ID for this client
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False

    def connect(self, max_retries=3):
        """Connect to IB with retry logic."""
        for attempt in range(max_retries):
            try:
                print(f"\nConnecting to IB (attempt {attempt + 1}/{max_retries})...")
                print(f"  Host: {self.host}")
                print(f"  Port: {self.port} ({'Paper' if self.port == 7497 else 'Live'})")

                self.ib.connect(self.host, self.port, clientId=self.client_id)
                self.connected = True

                print("✅ Connected successfully!")
                print(f"   Server time: {self.ib.reqCurrentTime()}")

                return True

            except Exception as e:
                print(f"❌ Connection failed: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("\n⚠️  Could not connect to IB.")
                    print("   Make sure TWS or IB Gateway is running.")
                    print("   Check that API is enabled in settings.")
                    return False

        return False

    def disconnect(self):
        """Disconnect from IB."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print("Disconnected from IB")

    def create_futures_contract(self, symbol='MES', exchange='CME', currency='USD',
                                continuous=False):
        """
        Create a futures contract.

        Args:
            symbol: MES, ES, NQ, etc.
            exchange: CME, NYMEX, etc.
            currency: USD
            continuous: If True, use continuous contract (CONTFUT) for long
                        historical data pulls that span multiple contract months.

        Returns:
            Contract object
        """
        if continuous:
            # Continuous futures automatically stitch together the correct
            # contract months, so historical data works across roll dates.
            contract = Contract()
            contract.symbol = symbol
            contract.secType = 'CONTFUT'
            contract.exchange = exchange
            contract.currency = currency

            print(f"\nGetting continuous contract details for {symbol}...")
            details = self.ib.reqContractDetails(contract)

            if not details:
                print(f"Could not find continuous contract for {symbol}")
                return None

            contract = details[0].contract
            print(f"Using continuous contract: {contract.localSymbol}")
            return contract

        # Standard: get nearest expiry
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'FUT'
        contract.exchange = exchange
        contract.currency = currency

        print(f"\nGetting contract details for {symbol}...")
        details = self.ib.reqContractDetails(contract)

        if not details:
            print(f"No contracts found for {symbol}")
            return None

        # Use first (nearest) contract
        contract = details[0].contract
        print(f"Using contract: {contract.localSymbol}")
        print(f"   Expiry: {contract.lastTradeDateOrContractMonth}")

        return contract

    def _parse_duration_to_months(self, duration_str):
        """Convert duration string to total months."""
        duration_str = duration_str.strip()
        parts = duration_str.split()

        if len(parts) != 2:
            raise ValueError(f"Invalid duration format: {duration_str}")

        amount = int(parts[0])
        unit = parts[1].upper()

        if unit in ['Y', 'YEAR', 'YEARS']:
            return amount * 12
        elif unit in ['M', 'MONTH', 'MONTHS']:
            return amount
        elif unit in ['W', 'WEEK', 'WEEKS']:
            return max(1, amount // 4)
        elif unit in ['D', 'DAY', 'DAYS']:
            return max(1, amount // 30)
        else:
            raise ValueError(f"Unknown duration unit: {unit}")

    def download_historical_data(self, contract, duration='5 Y', bar_size='5 mins',
                                 what_to_show='TRADES', use_rth=True):
        """
        Download historical data from IB with auto-chunking for large requests.

        Automatically breaks large requests into 3-month chunks to avoid timeouts.

        Args:
            contract: IB Contract object
            duration: '5 Y', '1 Y', '6 M', etc.
            bar_size: '5 mins', '15 mins', '1 hour', '1 day'
            what_to_show: 'TRADES', 'MIDPOINT', 'BID', 'ASK'
            use_rth: True = regular trading hours only

        Returns:
            pandas DataFrame with OHLCV data
        """
        print(f"\nDownloading historical data...")
        print(f"  Duration: {duration}")
        print(f"  Bar Size: {bar_size}")
        print(f"  Regular Hours Only: {use_rth}")

        # Parse total months needed
        try:
            total_months = self._parse_duration_to_months(duration)
        except ValueError as e:
            print(f"❌ {e}")
            return None

        # Determine chunk size (3 months is safe for 5min bars)
        chunk_months = 3

        # If request is small enough, download directly
        if total_months <= chunk_months:
            print(f"  Downloading in single request...")
            return self._download_single_chunk(
                contract, duration, bar_size, what_to_show, use_rth
            )

        # Large request - chunk it
        num_chunks = (total_months + chunk_months - 1) // chunk_months
        print(f"  Large request detected: Breaking into {num_chunks} chunks of {chunk_months} months each")

        all_data = []
        end_date = datetime.now()

        for chunk_num in range(num_chunks):
            chunk_duration = f"{chunk_months} M"

            print(f"\n  Chunk {chunk_num + 1}/{num_chunks}: Downloading {chunk_months} months ending {end_date.strftime('%Y-%m-%d')}...")

            try:
                # Download chunk
                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=end_date.strftime('%Y%m%d %H:%M:%S'),
                    durationStr=chunk_duration,
                    barSizeSetting=bar_size,
                    whatToShow=what_to_show,
                    useRTH=use_rth,
                    formatDate=1
                )

                if not bars:
                    print(f"    ⚠️  No data returned for chunk {chunk_num + 1}")
                    continue

                # Convert to DataFrame
                df_chunk = util.df(bars)
                all_data.append(df_chunk)

                print(f"    ✅ Downloaded {len(df_chunk)} bars")
                print(f"       Range: {df_chunk['date'].min()} to {df_chunk['date'].max()}")

                # Update end date for next chunk (move back 3 months)
                end_date = df_chunk['date'].min() - timedelta(seconds=1)

                # Rate limit: wait between chunks
                if chunk_num < num_chunks - 1:
                    time.sleep(2)

            except Exception as e:
                print(f"    ❌ Error downloading chunk {chunk_num + 1}: {e}")
                if chunk_num == 0:  # If first chunk fails, abort
                    return None
                # Otherwise continue with what we have
                break

        if not all_data:
            print("❌ No data retrieved from any chunk")
            return None

        # Combine all chunks
        print(f"\n  Combining {len(all_data)} chunks...")
        df = pd.concat(all_data, ignore_index=True)

        # Remove duplicates and sort
        df = df.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)

        print(f"\n✅ Downloaded {len(df)} total bars")
        print(f"   Date Range: {df['date'].min()} to {df['date'].max()}")
        print(f"   Price Range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")

        # Rename columns to match our format
        df = df.rename(columns={
            'date': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })

        # Set timestamp as index
        df = df.set_index('timestamp')

        # Keep only OHLCV
        df = df[['open', 'high', 'low', 'close', 'volume']]

        return df

    def _download_single_chunk(self, contract, duration, bar_size, what_to_show, use_rth):
        """Download a single chunk of data (internal helper)."""
        try:
            # Request data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=1
            )

            if not bars:
                print("❌ No data returned")
                return None

            # Convert to DataFrame
            df = util.df(bars)

            print(f"\n✅ Downloaded {len(df)} bars")
            print(f"   Date Range: {df['date'].min()} to {df['date'].max()}")
            print(f"   Price Range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")

            # Rename columns to match our format
            df = df.rename(columns={
                'date': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })

            # Set timestamp as index
            df = df.set_index('timestamp')

            # Keep only OHLCV
            df = df[['open', 'high', 'low', 'close', 'volume']]

            return df

        except Exception as e:
            print(f"❌ Error downloading data: {e}")
            return None

    def save_data(self, df, symbol='MES', bar_size='5min'):
        """Save data to CSV file."""
        if df is None or df.empty:
            print("❌ No data to save")
            return None

        # Create filename
        start_date = df.index[0].strftime('%Y-%m-%d')
        end_date = df.index[-1].strftime('%Y-%m-%d')
        filename = f"{symbol}_{bar_size}_{start_date}_to_{end_date}_REAL.csv"

        # Save to data/historical
        output_dir = "data/historical"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        df.to_csv(filepath)

        print(f"\n✅ Saved to: {filepath}")
        print(f"   {len(df)} bars")
        print(f"   {df.index[0]} to {df.index[-1]}")

        return filepath

    def get_account_summary(self):
        """Get account summary (for paper/live trading)."""
        if not self.connected:
            print("❌ Not connected to IB")
            return None

        print("\nFetching account summary...")

        account_values = self.ib.accountSummary()

        summary = {}
        for item in account_values:
            summary[item.tag] = item.value

        # Print key metrics
        print("\n📊 Account Summary:")
        print(f"  Net Liquidation: ${float(summary.get('NetLiquidation', 0)):,.2f}")
        print(f"  Available Funds: ${float(summary.get('AvailableFunds', 0)):,.2f}")
        print(f"  Buying Power: ${float(summary.get('BuyingPower', 0)):,.2f}")
        print(f"  Maintenance Margin: ${float(summary.get('MaintMarginReq', 0)):,.2f}")

        return summary

    def get_positions(self):
        """Get current positions."""
        if not self.connected:
            print("❌ Not connected to IB")
            return []

        positions = self.ib.positions()

        if not positions:
            print("No open positions")
            return []

        print("\n📍 Current Positions:")
        for pos in positions:
            print(f"  {pos.contract.symbol}: {pos.position} @ ${pos.avgCost:.2f}")

        return positions


def quick_setup_guide():
    """Print quick setup guide for IB."""
    print("\n" + "="*70)
    print("INTERACTIVE BROKERS QUICK SETUP GUIDE")
    print("="*70)
    print("\n1. DOWNLOAD IB GATEWAY (Recommended) or TWS")
    print("   https://www.interactivebrokers.com/en/trading/ibgateway-stable.php")
    print("\n2. INSTALL & LOGIN")
    print("   - Use your IB paper trading credentials")
    print("   - Paper account username/password")
    print("\n3. ENABLE API")
    print("   Gateway: File → Global Configuration → API → Settings")
    print("   ✓ Enable ActiveX and Socket Clients")
    print("   ✓ Socket Port: 7497 (paper) or 7496 (live)")
    print("   ✓ Master API Client ID: (leave blank or set to 0)")
    print("   ✓ Read-Only API: NO (uncheck)")
    print("   ✓ Download open orders on connection: YES")
    print("\n4. TRUSTED IPs")
    print("   Add to Trusted IPs: 127.0.0.1")
    print("\n5. RESTART IB GATEWAY")
    print("   Close and reopen for settings to take effect")
    print("\n6. TEST CONNECTION")
    print("   Run: python src/ib/ib_integration.py")
    print("\n" + "="*70)
    print("Port 7497 = Paper Trading (RECOMMENDED)")
    print("Port 7496 = Live Trading (BE CAREFUL!)")
    print("="*70 + "\n")


# Example usage / test function
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='IB Data Downloader')
    parser.add_argument('--port', type=int, default=7497,
                       help='IB port (7497=paper, 7496=live)')
    parser.add_argument('--symbol', default='MES',
                       help='Futures symbol (default: MES)')
    parser.add_argument('--duration', default='5 Y',
                       help='Duration (default: 5 Y)')
    parser.add_argument('--bar-size', default='5 mins',
                       help='Bar size (default: 5 mins)')
    parser.add_argument('--continuous', action='store_true',
                       help='Use continuous contract (auto-enabled for >6M duration)')
    parser.add_argument('--setup', action='store_true',
                       help='Show setup guide')

    args = parser.parse_args()

    if args.setup:
        quick_setup_guide()
        exit(0)

    # Create connection
    ib_conn = IBConnection(port=args.port)

    try:
        # Connect
        if not ib_conn.connect():
            print("\n❌ Could not connect to IB")
            print("   Run with --setup flag for configuration help:")
            print("   python src/ib/ib_integration.py --setup")
            exit(1)

        # Auto-enable continuous contract for durations > 6 months
        use_continuous = args.continuous
        try:
            months = ib_conn._parse_duration_to_months(args.duration)
            if months > 6 and not use_continuous:
                print(f"\nDuration is {months} months — auto-enabling continuous contract")
                print("  (needed to span multiple contract roll dates)")
                use_continuous = True
        except ValueError:
            pass

        # Create contract
        contract = ib_conn.create_futures_contract(args.symbol, continuous=use_continuous)
        if not contract:
            exit(1)

        # Download data
        df = ib_conn.download_historical_data(
            contract,
            duration=args.duration,
            bar_size=args.bar_size
        )

        if df is not None:
            # Save data
            filepath = ib_conn.save_data(df, args.symbol, args.bar_size.replace(' ', ''))

            print(f"\n✅ SUCCESS!")
            print(f"   Data saved to: {filepath}")
            print(f"   Ready for backtesting!")

        # Get account summary
        ib_conn.get_account_summary()

        # Check positions
        ib_conn.get_positions()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ib_conn.disconnect()

    print("\nDone!")
