"""
EMA 9 Crossover Strategy - MES/ES 5-min
========================================
Simple, fast momentum strategy using EMA 9 as the signal line.

Core logic:
  - LONG:  Close crosses above EMA 9 (bullish momentum shift)
  - SHORT: Close crosses below EMA 9 (bearish momentum shift)

Confirmation filters (prevent whipsaws in choppy markets):
  - ATR filter: require minimum volatility (avoid noise crossovers)
  - Volume filter: require above-average volume on crossover bar
  - ADX filter: optional trend strength confirmation
  - Minimum distance: price must move X% beyond EMA to confirm

Risk management:
  - Stop loss: ATR-based (gives room proportional to volatility)
  - Take profit: ATR multiple (momentum expected to continue)
  - Time exit: max bars in trade (don't hold stale signals)
  - Circuit breaker: pause after N consecutive losses

Design notes:
  - EMA 9 is fast-reacting, catches quick momentum shifts
  - On 5-min bars, this means ~45 minutes of lookback
  - Works best in trending/volatile conditions (complement to MR)
  - Whipsaw risk is the main concern - filters are critical
"""

import pandas as pd
import numpy as np
from typing import Dict
import sys
sys.path.append('src')
from strategies.base_strategy import BaseStrategy


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA 9 crossover strategy for MES/ES futures on 5-min timeframe.
    Trades momentum shifts when price crosses above/below EMA 9.
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # EMA parameters
        self.ema_period = config.get('ema_period', 9)

        # Crossover confirmation
        self.min_cross_distance_pct = config.get('min_cross_distance_pct', 0.02)  # % beyond EMA to confirm

        # Volume confirmation
        self.min_volume_ratio = config.get('min_volume_ratio', 0.0)  # 0 = off
        self.volume_ma_period = config.get('volume_ma_period', 20)

        # ATR filter
        self.atr_period = config.get('atr_period', 14)
        self.min_atr_for_entry = config.get('min_atr_for_entry', 0.0)  # 0 = off
        self.max_atr_for_entry = config.get('max_atr_for_entry', 0.0)  # 0 = off

        # Optional ADX trend filter
        self.use_adx_filter = config.get('use_adx_filter', False)
        self.adx_period = config.get('adx_period', 14)
        self.adx_min_threshold = config.get('adx_min_threshold', 20)

        # Risk management
        self.stop_loss_atr_multiple = config.get('stop_loss_atr_multiple', 2.0)
        self.take_profit_atr_multiple = config.get('take_profit_atr_multiple', 3.0)

        # Time filters
        self.allowed_hours = config.get('allowed_hours', [9, 10, 11, 12, 13, 14, 15])
        self.avoid_hours = config.get('avoid_hours', [])

        # Trade management
        self.max_trades_per_day = config.get('max_trades_per_day', 4)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 36)  # 3 hours

        # State
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.trades_today = 0
        self.daily_pnl = 0
        self.last_trade_date = None

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ADX for trend strength measurement."""
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        up_move = df['high'] - df['high'].shift()
        down_move = df['low'].shift() - df['low']

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window=period).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA and supporting indicators."""
        df = data.copy()

        print("Calculating EMA CROSSOVER indicators...")

        # EMA 9 (the signal line)
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # Previous bar's close relative to EMA (for detecting crossover)
        df['prev_close'] = df['close'].shift(1)
        df['prev_ema'] = df['ema'].shift(1)

        # Distance from EMA as percentage
        df['ema_distance_pct'] = ((df['close'] - df['ema']) / df['ema']) * 100

        # ATR for volatility measurement and stop sizing
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_period).mean()

        # Volume
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma_period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # ADX (optional)
        if self.use_adx_filter:
            df['adx'] = self.calculate_adx(df, self.adx_period)

        print(f"  EMA period: {self.ema_period}")
        print(f"  Min cross distance: {self.min_cross_distance_pct}%")
        print(f"  ATR period: {self.atr_period}")
        print(f"  Time filter: {self.allowed_hours}")

        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals on EMA 9 crossovers.

        LONG:  prev_close <= prev_ema AND close > ema + buffer (bullish cross)
        SHORT: prev_close >= prev_ema AND close < ema - buffer (bearish cross)
        """
        df = self.calculate_indicators(data)

        print("\nGenerating EMA CROSSOVER signals...")

        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan

        signals = {'long_cross': 0, 'short_cross': 0,
                   'skipped_distance': 0, 'skipped_volume': 0,
                   'skipped_atr': 0, 'skipped_time': 0,
                   'skipped_adx': 0}

        start_idx = max(self.ema_period + 5, 30)  # Need enough history for EMA + ATR

        for i in range(start_idx, len(df)):
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
                    print(f"\n[ALERT] CIRCUIT BREAKER at {bar.name}: {self.consecutive_losses} consecutive losses")
                continue

            # Daily trade limit
            if self.trades_today >= self.max_trades_per_day:
                continue

            # Time filter
            if self.avoid_hours and current_hour in self.avoid_hours:
                signals['skipped_time'] += 1
                continue
            if current_hour not in self.allowed_hours:
                continue

            # Get values
            close = bar['close']
            ema = bar['ema']
            prev_close = bar['prev_close']
            prev_ema = bar['prev_ema']
            atr = bar['atr']
            volume_ratio = bar['volume_ratio']

            # Skip missing data
            if pd.isna(ema) or pd.isna(prev_ema) or pd.isna(atr) or pd.isna(prev_close):
                continue

            # ATR filter
            if self.min_atr_for_entry > 0 and atr < self.min_atr_for_entry:
                signals['skipped_atr'] += 1
                continue
            if self.max_atr_for_entry > 0 and atr > self.max_atr_for_entry:
                signals['skipped_atr'] += 1
                continue

            # ADX filter (optional)
            if self.use_adx_filter:
                adx = bar.get('adx', 0)
                if pd.isna(adx) or adx < self.adx_min_threshold:
                    signals['skipped_adx'] += 1
                    continue

            # Volume filter
            if self.min_volume_ratio > 0:
                if pd.isna(volume_ratio) or volume_ratio < self.min_volume_ratio:
                    signals['skipped_volume'] += 1
                    continue

            # Detect crossover
            ema_distance_pct = abs((close - ema) / ema) * 100
            min_dist = self.min_cross_distance_pct

            # LONG: Bullish crossover (close crosses above EMA)
            if (prev_close <= prev_ema and close > ema and
                    ema_distance_pct >= min_dist):

                df.at[df.index[i], 'signal'] = 1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close - (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = close + (atr * self.take_profit_atr_multiple)
                signals['long_cross'] += 1
                self.trades_today += 1

            # SHORT: Bearish crossover (close crosses below EMA)
            elif (prev_close >= prev_ema and close < ema and
                  ema_distance_pct >= min_dist):

                df.at[df.index[i], 'signal'] = -1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close + (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = close - (atr * self.take_profit_atr_multiple)
                signals['short_cross'] += 1
                self.trades_today += 1

        total = signals['long_cross'] + signals['short_cross']
        print(f"\n  Total signals: {total}")
        print(f"  Long crossovers:  {signals['long_cross']}")
        print(f"  Short crossovers: {signals['short_cross']}")
        print(f"  Skipped (ATR):    {signals['skipped_atr']}")
        print(f"  Skipped (ADX):    {signals['skipped_adx']}")
        print(f"  Skipped (vol):    {signals['skipped_volume']}")
        print(f"  Skipped (dist):   {signals['skipped_distance']}")
        print(f"  Skipped (time):   {signals['skipped_time']}")

        return df

    def get_exit_price(self, entry_price: float, stop_loss: float,
                       take_profit: float, bars_in_trade: int,
                       data_slice: pd.DataFrame) -> tuple:
        """
        Exit logic: stop loss, take profit, or time exit.
        Simple exits for a simple strategy - no trailing stop initially.
        """
        bar = data_slice.iloc[0]
        current_high = bar['high']
        current_low = bar['low']
        current_close = bar['close']

        is_long = stop_loss < entry_price

        # Hard stop loss
        if is_long and current_low <= stop_loss:
            return stop_loss, 'stop_loss'
        elif not is_long and current_high >= stop_loss:
            return stop_loss, 'stop_loss'

        # Take profit
        if is_long and current_high >= take_profit:
            return take_profit, 'take_profit'
        elif not is_long and current_low <= take_profit:
            return take_profit, 'take_profit'

        # Time exit
        if bars_in_trade >= self.config.get('max_bars_in_trade', 36):
            return current_close, 'time_exit'

        return None, None

    def record_trade_result(self, pnl: float):
        """Track consecutive losses for circuit breaker."""
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            self.circuit_breaker_active = False
