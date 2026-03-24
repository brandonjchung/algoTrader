"""
Regime Analysis Tool

Analyzes WHY strategy performance degrades over time.
Instead of optimizing parameters in hindsight, understand market regime shifts.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime
import sys


class RegimeAnalyzer:
    """
    Analyze market regime changes and strategy performance correlation.
    """

    def __init__(self, trades_file, data_file):
        """
        Initialize analyzer.

        Args:
            trades_file: CSV file with trade results
            data_file: CSV file with market data
        """
        # Load trades
        self.trades = pd.read_csv(trades_file)
        self.trades['entry_time'] = pd.to_datetime(self.trades['entry_time'], utc=True)
        self.trades['exit_time'] = pd.to_datetime(self.trades['exit_time'], utc=True)
        # Convert to timezone-naive
        if self.trades['entry_time'].dt.tz is not None:
            self.trades['entry_time'] = self.trades['entry_time'].dt.tz_localize(None)
            self.trades['exit_time'] = self.trades['exit_time'].dt.tz_localize(None)

        # Load market data
        self.data = pd.read_csv(f"data/historical/{data_file}")
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'], utc=True)
        # Convert to timezone-naive
        if self.data['timestamp'].dt.tz is not None:
            self.data['timestamp'] = self.data['timestamp'].dt.tz_localize(None)
        self.data = self.data.set_index('timestamp')

        # Calculate equity curve
        self.trades['cumulative_pnl'] = self.trades['pnl'].cumsum()
        self.trades['trade_number'] = range(1, len(self.trades) + 1)

        print(f"Loaded {len(self.trades)} trades")
        print(f"Loaded {len(self.data)} market bars")

    def calculate_market_metrics(self):
        """Calculate market regime indicators."""
        print("\nCalculating market regime metrics...")

        # ATR (volatility)
        self.data['tr'] = np.maximum(
            self.data['high'] - self.data['low'],
            np.maximum(
                abs(self.data['high'] - self.data['close'].shift(1)),
                abs(self.data['low'] - self.data['close'].shift(1))
            )
        )
        self.data['atr'] = self.data['tr'].rolling(14).mean()

        # Trend strength (ADX-like)
        delta = self.data['close'].diff()
        self.data['trend_strength'] = delta.rolling(20).std()

        # Volume
        self.data['volume_ma'] = self.data['volume'].rolling(20).mean()
        self.data['volume_ratio'] = self.data['volume'] / self.data['volume_ma']

        # Hour of day
        self.data['hour'] = self.data.index.hour

        # Day of week
        self.data['day_of_week'] = self.data.index.dayofweek

        print("  ✅ Market metrics calculated")

    def find_regime_shifts(self):
        """Identify when market regime significantly changed."""
        print("\nIdentifying regime shifts...")

        # Calculate rolling statistics
        window = 100  # 100 bars = ~8.5 hours

        self.data['atr_ma'] = self.data['atr'].rolling(window).mean()
        self.data['atr_std'] = self.data['atr'].rolling(window).std()

        # Regime shift = ATR changes by >2 std devs
        self.data['atr_zscore'] = (self.data['atr'] - self.data['atr_ma']) / self.data['atr_std']
        self.data['regime_shift'] = abs(self.data['atr_zscore']) > 2.0

        shifts = self.data[self.data['regime_shift']]
        print(f"  Found {len(shifts)} regime shifts")

        return shifts

    def analyze_performance_by_regime(self):
        """Analyze strategy performance in different market regimes."""
        print("\nAnalyzing performance by market regime...")

        # Merge trades with market conditions at entry
        trades_with_regime = []

        for _, trade in self.trades.iterrows():
            # Find market conditions at entry
            entry_time = trade['entry_time']

            # Find closest market bar
            if entry_time in self.data.index:
                market_bar = self.data.loc[entry_time]
            else:
                # Find nearest
                idx = self.data.index.get_indexer([entry_time], method='nearest')[0]
                market_bar = self.data.iloc[idx]

            trade_data = trade.to_dict()
            trade_data['entry_atr'] = market_bar['atr']
            trade_data['entry_trend'] = market_bar['trend_strength']
            trade_data['entry_volume_ratio'] = market_bar['volume_ratio']
            trade_data['entry_hour'] = market_bar['hour']

            trades_with_regime.append(trade_data)

        self.trades_enriched = pd.DataFrame(trades_with_regime)

        # Analyze by ATR quintiles (volatility regimes)
        self.trades_enriched['atr_quintile'] = pd.qcut(
            self.trades_enriched['entry_atr'],
            q=5,
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
        )

        print("\n" + "="*60)
        print("PERFORMANCE BY VOLATILITY REGIME (ATR)")
        print("="*60)

        regime_stats = self.trades_enriched.groupby('atr_quintile').agg({
            'pnl': ['count', 'sum', 'mean'],
            'direction': lambda x: (x == 'LONG').sum()
        })

        regime_stats.columns = ['Trades', 'Total P&L', 'Avg P&L', 'LONG Count']
        regime_stats['Win Rate %'] = (
            self.trades_enriched.groupby('atr_quintile')['pnl']
            .apply(lambda x: (x > 0).sum() / len(x) * 100)
        )

        print(regime_stats)

        # Find best and worst regimes
        best_regime = regime_stats['Avg P&L'].idxmax()
        worst_regime = regime_stats['Avg P&L'].idxmin()

        print(f"\n✅ Best performance in: {best_regime} volatility")
        print(f"❌ Worst performance in: {worst_regime} volatility")

    def analyze_equity_curve_phases(self):
        """Identify when equity curve changed behavior."""
        print("\n" + "="*60)
        print("EQUITY CURVE PHASE ANALYSIS")
        print("="*60)

        # Find peak
        peak_idx = self.trades['cumulative_pnl'].idxmax()
        peak_trade = peak_idx + 1
        peak_pnl = self.trades.loc[peak_idx, 'cumulative_pnl']

        print(f"\nPeak Performance:")
        print(f"  Trade #{peak_trade}")
        print(f"  Cumulative P&L: ${peak_pnl:.2f}")
        print(f"  Date: {self.trades.loc[peak_idx, 'exit_time']}")

        # Split into before/after peak
        before_peak = self.trades.iloc[:peak_idx+1]
        after_peak = self.trades.iloc[peak_idx+1:]

        print(f"\nBefore Peak ({len(before_peak)} trades):")
        self._print_phase_stats(before_peak)

        print(f"\nAfter Peak ({len(after_peak)} trades):")
        self._print_phase_stats(after_peak)

        # Compare regimes
        if len(after_peak) > 0 and hasattr(self, 'trades_enriched'):
            print(f"\nRegime Comparison:")

            before_atr = self.trades_enriched.iloc[:peak_idx+1]['entry_atr'].mean()
            after_atr = self.trades_enriched.iloc[peak_idx+1:]['entry_atr'].mean()

            print(f"  Before Peak Avg ATR: {before_atr:.2f}")
            print(f"  After Peak Avg ATR: {after_atr:.2f}")
            print(f"  Change: {((after_atr - before_atr) / before_atr * 100):.1f}%")

            if after_atr > before_atr * 1.2:
                print("  ⚠️  Volatility INCREASED significantly - strategy struggled")
            elif after_atr < before_atr * 0.8:
                print("  ⚠️  Volatility DECREASED significantly - strategy struggled")
            else:
                print("  ℹ️  Volatility relatively stable - degradation not volatility-driven")

    def _print_phase_stats(self, df):
        """Print statistics for a phase."""
        total_pnl = df['pnl'].sum()
        win_rate = (df['pnl'] > 0).sum() / len(df) * 100
        avg_win = df[df['pnl'] > 0]['pnl'].mean() if len(df[df['pnl'] > 0]) > 0 else 0
        avg_loss = df[df['pnl'] < 0]['pnl'].mean() if len(df[df['pnl'] < 0]) > 0 else 0

        wins = df[df['pnl'] > 0]['pnl'].sum()
        losses = abs(df[df['pnl'] < 0]['pnl'].sum())
        pf = wins / losses if losses > 0 else 0

        print(f"  Total P&L: ${total_pnl:.2f}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Profit Factor: {pf:.2f}")
        print(f"  Avg Win: ${avg_win:.2f}")
        print(f"  Avg Loss: ${avg_loss:.2f}")

    def generate_visualizations(self, output_prefix="regime_analysis"):
        """Generate regime analysis charts."""
        print("\nGenerating visualizations...")

        fig, axes = plt.subplots(3, 1, figsize=(14, 10))

        # 1. Equity curve with ATR overlay
        ax1 = axes[0]
        ax1_twin = ax1.twinx()

        ax1.plot(self.trades['trade_number'], self.trades['cumulative_pnl'], 'b-', linewidth=2)
        ax1.set_xlabel('Trade Number')
        ax1.set_ylabel('Cumulative P&L ($)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='k', linestyle='--', alpha=0.3)

        # Plot avg ATR at each trade
        if hasattr(self, 'trades_enriched'):
            ax1_twin.plot(
                self.trades_enriched['trade_number'],
                self.trades_enriched['entry_atr'],
                'r-', alpha=0.5, linewidth=1
            )
            ax1_twin.set_ylabel('ATR at Entry', color='r')
            ax1_twin.tick_params(axis='y', labelcolor='r')

        ax1.set_title('Equity Curve vs Market Volatility (ATR)')

        # 2. Performance by hour
        ax2 = axes[1]
        if hasattr(self, 'trades_enriched'):
            hourly_pnl = self.trades_enriched.groupby('entry_hour')['pnl'].sum()
            hourly_pnl.plot(kind='bar', ax=ax2, color='steelblue')
            ax2.set_xlabel('Hour of Day')
            ax2.set_ylabel('Total P&L ($)')
            ax2.set_title('Performance by Hour of Day')
            ax2.axhline(y=0, color='k', linestyle='--', alpha=0.3)
            ax2.grid(True, alpha=0.3, axis='y')

        # 3. Win rate by volatility regime
        ax3 = axes[2]
        if hasattr(self, 'trades_enriched'):
            regime_wr = self.trades_enriched.groupby('atr_quintile').apply(
                lambda x: (x['pnl'] > 0).sum() / len(x) * 100
            )
            regime_wr.plot(kind='bar', ax=ax3, color='green', alpha=0.7)
            ax3.set_xlabel('Volatility Regime')
            ax3.set_ylabel('Win Rate (%)')
            ax3.set_title('Win Rate by Volatility Regime')
            ax3.axhline(y=50, color='k', linestyle='--', alpha=0.3, label='50% baseline')
            ax3.grid(True, alpha=0.3, axis='y')
            ax3.legend()

        plt.tight_layout()
        output_file = f"{output_prefix}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"  ✅ Saved {output_file}")
        plt.close()

    def run_full_analysis(self):
        """Run complete regime analysis."""
        print("\n" + "="*60)
        print("REGIME ANALYSIS")
        print("="*60)

        self.calculate_market_metrics()
        self.find_regime_shifts()
        self.analyze_performance_by_regime()
        self.analyze_equity_curve_phases()
        self.generate_visualizations()

        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        print("\nKey Insights:")
        print("1. Check regime_analysis.png for visual patterns")
        print("2. Look for volatility regime that strategy struggles in")
        print("3. Identify if degradation is time-based or regime-based")
        print("4. Use this to build ADAPTIVE logic, not optimized parameters")
        print("="*60 + "\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: python regime_analysis.py <trades_file> <data_file>")
        print("\nExample:")
        print("  python regime_analysis.py logs/trades_20260216_001216.csv MES_5mins_2025-02-14_to_2026-02-13_REAL.csv")
        sys.exit(1)

    trades_file = sys.argv[1]
    data_file = sys.argv[2]

    analyzer = RegimeAnalyzer(trades_file, data_file)
    analyzer.run_full_analysis()


if __name__ == '__main__':
    main()
