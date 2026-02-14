"""
InfluxDB Metrics Writer

Sends trading metrics to InfluxDB for visualization in Grafana.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MetricsWriter:
    """Writes trading metrics to InfluxDB"""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None
    ):
        """
        Initialize InfluxDB connection

        Args:
            url: InfluxDB URL (default: from env INFLUXDB_URL)
            token: InfluxDB token (default: from env INFLUXDB_TOKEN)
            org: InfluxDB organization (default: from env INFLUXDB_ORG)
            bucket: InfluxDB bucket (default: from env INFLUXDB_BUCKET)
        """
        self.url = url or os.getenv('INFLUXDB_URL', 'http://localhost:8086')
        self.token = token or os.getenv('INFLUXDB_TOKEN')
        self.org = org or os.getenv('INFLUXDB_ORG', 'AlgoTrader')
        self.bucket = bucket or os.getenv('INFLUXDB_BUCKET', 'trading_metrics')

        if not self.token:
            raise ValueError("InfluxDB token not found. Set INFLUXDB_TOKEN in .env file")

        self.client = None
        self.write_api = None
        self._connect()

    def _connect(self):
        """Establish connection to InfluxDB"""
        try:
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

            # Test connection
            health = self.client.health()
            if health.status != "pass":
                raise ConnectionError(f"InfluxDB health check failed: {health.message}")

            print(f"✅ Connected to InfluxDB at {self.url}")

        except Exception as e:
            print(f"❌ Failed to connect to InfluxDB: {e}")
            raise

    def write_trade(
        self,
        trade_data: Dict,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write a single trade to InfluxDB

        Args:
            trade_data: Dictionary with trade information
            timestamp: Trade timestamp (default: now)

        Returns:
            True if successful, False otherwise

        Example:
            trade_data = {
                'symbol': 'MES',
                'direction': 'LONG',
                'entry_price': 5123.50,
                'exit_price': 5128.75,
                'pnl': 125.00,
                'pnl_percent': 1.25,
                'quantity': 1,
                'exit_reason': 'take_profit',
                'duration_minutes': 45
            }
        """
        try:
            point = Point("trade")

            # Add tags (indexed, for filtering)
            point.tag("symbol", trade_data.get('symbol', 'UNKNOWN'))
            point.tag("direction", trade_data.get('direction', 'UNKNOWN'))
            point.tag("exit_reason", trade_data.get('exit_reason', 'unknown'))
            point.tag("strategy", trade_data.get('strategy', 'unknown'))

            # Add fields (not indexed, for values)
            point.field("entry_price", float(trade_data.get('entry_price', 0)))
            point.field("exit_price", float(trade_data.get('exit_price', 0)))
            point.field("pnl", float(trade_data.get('pnl', 0)))
            point.field("pnl_percent", float(trade_data.get('pnl_percent', 0)))
            point.field("quantity", int(trade_data.get('quantity', 1)))
            point.field("duration_minutes", int(trade_data.get('duration_minutes', 0)))
            point.field("commission", float(trade_data.get('commission', 0)))
            point.field("slippage", float(trade_data.get('slippage', 0)))

            # MAE/MFE if available
            if 'mae' in trade_data:
                point.field("mae", float(trade_data['mae']))
            if 'mfe' in trade_data:
                point.field("mfe", float(trade_data['mfe']))

            # Set timestamp
            if timestamp:
                point.time(timestamp, WritePrecision.NS)

            # Write to InfluxDB
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True

        except Exception as e:
            print(f"❌ Error writing trade: {e}")
            return False

    def write_equity(
        self,
        equity: float,
        cash: float,
        drawdown_pct: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write equity curve data point

        Args:
            equity: Current equity value
            cash: Current cash value
            drawdown_pct: Current drawdown percentage
            timestamp: Data timestamp (default: now)
        """
        try:
            point = Point("equity") \
                .field("total_equity", float(equity)) \
                .field("cash", float(cash)) \
                .field("drawdown_pct", float(drawdown_pct))

            if timestamp:
                point.time(timestamp, WritePrecision.NS)

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True

        except Exception as e:
            print(f"❌ Error writing equity: {e}")
            return False

    def write_performance(
        self,
        metrics: Dict,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write performance metrics

        Args:
            metrics: Dictionary with performance metrics
            timestamp: Data timestamp (default: now)

        Example:
            metrics = {
                'total_trades': 215,
                'win_rate': 63.72,
                'profit_factor': 2.69,
                'sharpe_ratio': 1.89,
                'max_drawdown': 10.17,
                'total_return': 219.38,
                'avg_win': 87.50,
                'avg_loss': -32.50,
                'largest_win': 250.00,
                'largest_loss': -125.00
            }
        """
        try:
            point = Point("performance")

            # Add all metrics as fields
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    point.field(key, float(value))

            if timestamp:
                point.time(timestamp, WritePrecision.NS)

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True

        except Exception as e:
            print(f"❌ Error writing performance: {e}")
            return False

    def write_position(
        self,
        symbol: str,
        direction: str,
        quantity: int,
        entry_price: float,
        current_price: float,
        unrealized_pnl: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write open position data

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            quantity: Position size
            entry_price: Entry price
            current_price: Current market price
            unrealized_pnl: Unrealized profit/loss
            timestamp: Data timestamp (default: now)
        """
        try:
            point = Point("position") \
                .tag("symbol", symbol) \
                .tag("direction", direction) \
                .field("quantity", int(quantity)) \
                .field("entry_price", float(entry_price)) \
                .field("current_price", float(current_price)) \
                .field("unrealized_pnl", float(unrealized_pnl))

            if timestamp:
                point.time(timestamp, WritePrecision.NS)

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True

        except Exception as e:
            print(f"❌ Error writing position: {e}")
            return False

    def write_system_status(
        self,
        status: str,
        circuit_breaker_active: bool = False,
        consecutive_losses: int = 0,
        message: str = "",
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write system status (for monitoring health)

        Args:
            status: System status (running, stopped, error)
            circuit_breaker_active: Whether circuit breaker is active
            consecutive_losses: Number of consecutive losses
            message: Status message
            timestamp: Data timestamp (default: now)
        """
        try:
            point = Point("system_status") \
                .tag("status", status) \
                .field("circuit_breaker_active", int(circuit_breaker_active)) \
                .field("consecutive_losses", int(consecutive_losses)) \
                .field("message", str(message))

            if timestamp:
                point.time(timestamp, WritePrecision.NS)

            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True

        except Exception as e:
            print(f"❌ Error writing system status: {e}")
            return False

    def write_batch(self, points: List[Point]) -> bool:
        """
        Write multiple points in a batch

        Args:
            points: List of Point objects

        Returns:
            True if successful, False otherwise
        """
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
            return True
        except Exception as e:
            print(f"❌ Error writing batch: {e}")
            return False

    def close(self):
        """Close InfluxDB connection"""
        if self.client:
            self.client.close()
            print("✅ Closed InfluxDB connection")


def test_metrics_writer():
    """Test the metrics writer with sample data"""
    print("\n🧪 Testing MetricsWriter...\n")

    try:
        # Initialize writer
        writer = MetricsWriter()

        # Test 1: Write sample trade
        print("Test 1: Writing sample trade...")
        trade_data = {
            'symbol': 'MES',
            'direction': 'LONG',
            'strategy': 'volatility_breakout_improved',
            'entry_price': 5123.50,
            'exit_price': 5128.75,
            'pnl': 125.00,
            'pnl_percent': 1.25,
            'quantity': 1,
            'exit_reason': 'take_profit',
            'duration_minutes': 45,
            'commission': 1.20,
            'slippage': 2.50,
            'mae': -15.00,
            'mfe': 137.50
        }
        success = writer.write_trade(trade_data)
        print(f"{'✅' if success else '❌'} Trade written")

        # Test 2: Write equity data
        print("\nTest 2: Writing equity data...")
        success = writer.write_equity(
            equity=10125.00,
            cash=9875.00,
            drawdown_pct=1.25
        )
        print(f"{'✅' if success else '❌'} Equity written")

        # Test 3: Write performance metrics
        print("\nTest 3: Writing performance metrics...")
        metrics = {
            'total_trades': 215,
            'win_rate': 63.72,
            'profit_factor': 2.69,
            'sharpe_ratio': 1.89,
            'max_drawdown': 10.17,
            'total_return': 219.38,
            'avg_win': 87.50,
            'avg_loss': -32.50,
            'largest_win': 250.00,
            'largest_loss': -125.00
        }
        success = writer.write_performance(metrics)
        print(f"{'✅' if success else '❌'} Performance metrics written")

        # Test 4: Write open position
        print("\nTest 4: Writing open position...")
        success = writer.write_position(
            symbol='MES',
            direction='LONG',
            quantity=1,
            entry_price=5123.50,
            current_price=5126.25,
            unrealized_pnl=68.75
        )
        print(f"{'✅' if success else '❌'} Position written")

        # Test 5: Write system status
        print("\nTest 5: Writing system status...")
        success = writer.write_system_status(
            status='running',
            circuit_breaker_active=False,
            consecutive_losses=0,
            message='System operating normally'
        )
        print(f"{'✅' if success else '❌'} System status written")

        # Close connection
        writer.close()

        print("\n✅ All tests passed!")
        print("\n📊 Check Grafana dashboard at: http://localhost:3000")
        print("   (Refresh dashboard to see test data)\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='InfluxDB Metrics Writer')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    args = parser.parse_args()

    if args.test:
        test_metrics_writer()
    else:
        print("Usage: python metrics_writer.py --test")
        print("\nThis module is typically imported and used by the backtester or trading bot.")
        print("Run with --test flag to verify InfluxDB connection and write sample data.")
