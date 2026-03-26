"""
Adaptive Mean Reversion Strategy - Percentile-Based Filters

DESIGN PHILOSOPHY:
Instead of hardcoded thresholds (ATR < 5.0, volume < 0.9x) that break when
market regimes shift, this strategy uses rolling percentile-based filters
that automatically adapt to current conditions.

- "Trade when ATR is below the 75th percentile" works whether ATR averages
  3.0 or 6.0, because the threshold adjusts with the data.
- "Trade when volume is below the 50th percentile" captures quiet bars
  regardless of absolute volume levels.

Core logic remains the same: mean reversion at Bollinger Band extremes
during quiet, low-volatility conditions at historically profitable hours.
"""

import pandas as pd
import numpy as np
from typing import Dict
import sys
sys.path.append('src')
from strategies.base_strategy import BaseStrategy


class AdaptiveMeanReversion(BaseStrategy):
    """
    Mean reversion strategy with self-calibrating percentile-based filters.
    No fixed thresholds — adapts to any market regime automatically.
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # Core signal parameters
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_oversold = config.get('rsi_oversold', 35)
        self.rsi_overbought = config.get('rsi_overbought', 65)
        self.bb_period = config.get('bb_period', 20)
        self.bb_std = config.get('bb_std', 2.0)
        self.atr_period = config.get('atr_period', 14)

        # ADAPTIVE FILTERS (percentile-based, not absolute)
        self.adaptive_lookback = config.get('adaptive_lookback', 500)  # ~4 trading days of 5-min bars
        self.max_atr_percentile = config.get('max_atr_percentile', 75)  # Trade below 75th pctl
        self.min_atr_percentile = config.get('min_atr_percentile', 10)  # Skip dead markets
        self.max_volume_percentile = config.get('max_volume_percentile', 50)  # Trade quiet bars

        # Risk management (ATR multiples are relative by nature, no change needed)
        self.stop_loss_atr_multiple = config.get('stop_loss_atr_multiple', 3.0)
        self.take_profit_atr_multiple = config.get('take_profit_atr_multiple', 3.5)
        self.use_atr_take_profit = config.get('use_atr_take_profit', False)

        # Time filters
        self.allowed_hours = config.get('allowed_hours', [13, 16, 21])
        self.avoid_hours = config.get('avoid_hours', [14, 17, 19])
        self.avoid_weekdays = config.get('avoid_weekdays', [])

        # Risk limits
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 2.0)
        self.max_trades_per_day = config.get('max_trades_per_day', 3)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 60)

        # State tracking
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.daily_pnl = 0
        self.trades_today = 0
        self.last_trade_date = None

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators including rolling percentiles."""
        df = data.copy()

        print("Calculating ADAPTIVE MEAN REVERSION indicators...")

        # RSI
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=self.bb_period).mean()
        bb_std = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (self.bb_std * bb_std)
        df['bb_lower'] = df['bb_middle'] - (self.bb_std * bb_std)

        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(window=self.atr_period).mean()

        # Volume ratio
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # ADAPTIVE: Rolling percentiles for ATR and volume
        lookback = self.adaptive_lookback
        df['atr_pctl'] = df['atr'].rolling(window=lookback, min_periods=100).rank(pct=True) * 100
        df['volume_pctl'] = df['volume_ratio'].rolling(window=lookback, min_periods=100).rank(pct=True) * 100

        print(f"  RSI({self.rsi_period}) + BB({self.bb_period}, {self.bb_std}std)")
        print(f"  Adaptive filters: ATR <{self.max_atr_percentile}th pctl, "
              f"Vol <{self.max_volume_percentile}th pctl "
              f"(lookback={lookback} bars)")
        print(f"  Time filters: {self.allowed_hours}")

        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals with adaptive percentile-based filtering."""
        df = self.calculate_indicators(data)

        print("\nGenerating ADAPTIVE signals...")

        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan

        counts = {
            'long': 0, 'short': 0,
            'skipped_atr': 0, 'skipped_vol': 0, 'skipped_time': 0
        }

        for i in range(self.adaptive_lookback, len(df)):
            bar = df.iloc[i]
            current_date = bar.name.date()
            current_hour = bar.name.hour

            # Reset daily counters
            if self.last_trade_date is None or current_date != self.last_trade_date:
                self.trades_today = 0
                self.daily_pnl = 0
                self.last_trade_date = current_date

            # Circuit breaker
            if self.consecutive_losses >= self.max_consecutive_losses:
                if not self.circuit_breaker_active:
                    self.circuit_breaker_active = True
                continue

            # Daily limits
            if self.daily_pnl < -self.max_daily_loss_pct:
                continue
            if self.trades_today >= self.max_trades_per_day:
                continue

            # Time filter
            if current_hour in self.avoid_hours:
                counts['skipped_time'] += 1
                continue
            if current_hour not in self.allowed_hours:
                continue

            # Weekday filter
            if self.avoid_weekdays and bar.name.weekday() in self.avoid_weekdays:
                continue

            # Skip missing data
            rsi = bar['rsi']
            atr = bar['atr']
            atr_pctl = bar['atr_pctl']
            vol_pctl = bar['volume_pctl']
            if pd.isna(rsi) or pd.isna(atr) or pd.isna(atr_pctl) or pd.isna(vol_pctl):
                continue

            # ADAPTIVE ATR FILTER: skip if ATR percentile too high or too low
            if atr_pctl > self.max_atr_percentile or atr_pctl < self.min_atr_percentile:
                counts['skipped_atr'] += 1
                continue

            # ADAPTIVE VOLUME FILTER: skip if volume percentile too high
            if vol_pctl > self.max_volume_percentile:
                counts['skipped_vol'] += 1
                continue

            close = bar['close']
            bb_upper = bar['bb_upper']
            bb_lower = bar['bb_lower']
            bb_middle = bar['bb_middle']

            # Take profit: ATR-based or BB middle
            if self.use_atr_take_profit:
                long_tp = close + (atr * self.take_profit_atr_multiple)
                short_tp = close - (atr * self.take_profit_atr_multiple)
            else:
                long_tp = bb_middle
                short_tp = bb_middle

            # LONG: oversold + below lower BB
            if rsi < self.rsi_oversold and close < bb_lower:
                df.at[df.index[i], 'signal'] = 1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close - (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = long_tp
                counts['long'] += 1
                self.trades_today += 1

            # SHORT: overbought + above upper BB
            elif rsi > self.rsi_overbought and close > bb_upper:
                df.at[df.index[i], 'signal'] = -1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close + (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = short_tp
                counts['short'] += 1
                self.trades_today += 1

        total = counts['long'] + counts['short']
        print(f"\n  Total signals: {total}")
        print(f"  LONG: {counts['long']}, SHORT: {counts['short']}")
        print(f"  Filtered by ATR percentile: {counts['skipped_atr']}")
        print(f"  Filtered by volume percentile: {counts['skipped_vol']}")
        print(f"  Filtered by time: {counts['skipped_time']}")

        return df

    def get_exit_price(self, entry_price: float, stop_loss: float,
                       take_profit: float, bars_in_trade: int,
                       data_slice: pd.DataFrame) -> tuple:
        """Exit logic: stop loss, take profit, or time exit."""
        bar = data_slice.iloc[0]
        is_long = stop_loss < entry_price

        # Stop loss
        if is_long and bar['low'] <= stop_loss:
            return stop_loss, 'stop_loss'
        elif not is_long and bar['high'] >= stop_loss:
            return stop_loss, 'stop_loss'

        # Take profit
        if is_long and bar['high'] >= take_profit:
            return take_profit, 'take_profit'
        elif not is_long and bar['low'] <= take_profit:
            return take_profit, 'take_profit'

        # Time exit
        if bars_in_trade >= self.max_bars_in_trade:
            return bar['close'], 'time_exit'

        return None, None

    def record_trade_result(self, pnl: float):
        """Track consecutive losses for circuit breaker."""
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            if self.circuit_breaker_active:
                self.circuit_breaker_active = False
