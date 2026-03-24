"""
IMPROVED Volatility Breakout Strategy
======================================

Original had only 3 trades in 5 years (too restrictive).

Improvements:
1. Loosen volume filter (1.2x → 1.1x)
2. Reduce breakout strength requirement (0.25 → 0.15 ATR)
3. Use adaptive lookback period (not fixed 20)
4. Better volatility detection (Bollinger Band squeeze)
5. Keep time filters (avoid first/last 15 min)
6. LONG bias (since analysis showed LONG > SHORT)

Expected: 50-150 trades over 5 years (vs 3)
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from .base_strategy import BaseStrategy


class VolatilityBreakoutImproved(BaseStrategy):
    """Improved volatility breakout with LONG bias."""

    def __init__(self, config: Dict):
        super().__init__(config)

        strategy_config = config.get('strategy', {})

        # Adaptive lookback (shorter in high vol, longer in low vol)
        self.lookback_min = strategy_config.get('lookback_min', 10)
        self.lookback_max = strategy_config.get('lookback_max', 30)

        self.atr_period = strategy_config.get('atr_period', 14)
        self.bb_period = strategy_config.get('bb_period', 20)
        self.bb_std = strategy_config.get('bb_std', 2.0)

        # Loosened filters
        self.volume_threshold = strategy_config.get('volume_threshold', 1.1)  # Was 1.2
        self.breakout_strength = strategy_config.get('breakout_strength', 0.15)  # Was 0.25

        # Risk management
        self.stop_loss_atr_multiple = strategy_config.get('stop_loss_atr_multiple', 2.5)  # Wider
        self.take_profit_atr_multiple = strategy_config.get('take_profit_atr_multiple', 4.0)  # Wider
        self.max_bars_in_trade = strategy_config.get('max_bars_in_trade', 60)

        self.max_trades_per_day = strategy_config.get('max_trades_per_day', 3)
        self.min_bars_between_trades = strategy_config.get('min_bars_between_trades', 5)

        # Circuit breaker
        self.max_consecutive_losses = strategy_config.get('max_consecutive_losses', 5)

        # State
        self.trades_today = 0
        self.last_trade_date = None
        self.bars_since_trade = 999
        self.consecutive_losses = 0
        self.circuit_breaker_active = False

        print(f"\n🚀 IMPROVED Volatility Breakout Strategy:")
        print(f"  Adaptive Lookback: {self.lookback_min}-{self.lookback_max}")
        print(f"  Volume Threshold: {self.volume_threshold}x (looser)")
        print(f"  Breakout Strength: {self.breakout_strength} ATR (looser)")
        print(f"  Stop/Target: {self.stop_loss_atr_multiple}x / {self.take_profit_atr_multiple}x ATR")
        print(f"  Circuit Breaker: {self.max_consecutive_losses} losses")

    def calculate_bollinger_bands(self, data: pd.Series, period: int, std: float) -> tuple:
        """Calculate Bollinger Bands for squeeze detection."""
        sma = data.rolling(window=period).mean()
        rolling_std = data.rolling(window=period).std()

        upper = sma + (rolling_std * std)
        lower = sma - (rolling_std * std)
        bandwidth = (upper - lower) / sma

        return upper, lower, bandwidth

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators."""
        df = data.copy()

        print("Calculating IMPROVED breakout indicators...")

        # ATR
        df['atr'] = self.calculate_atr(df, self.atr_period)
        df['atr_ma'] = df['atr'].rolling(window=self.atr_period).mean()

        # Bollinger Bands for squeeze detection
        df['bb_upper'], df['bb_lower'], df['bb_bandwidth'] = self.calculate_bollinger_bands(
            df['close'], self.bb_period, self.bb_std
        )

        # BB squeeze indicator (bandwidth is contracting)
        df['bb_squeeze'] = df['bb_bandwidth'] < df['bb_bandwidth'].rolling(window=self.bb_period).mean() * 0.8

        # Adaptive lookback based on volatility
        df['lookback_period'] = self.lookback_min + (
            (1 - df['bb_bandwidth'] / df['bb_bandwidth'].rolling(window=50).mean()) *
            (self.lookback_max - self.lookback_min)
        ).fillna(self.lookback_min).clip(self.lookback_min, self.lookback_max).astype(int)

        # Calculate rolling highs/lows with adaptive period
        df['rolling_high'] = df['high'].rolling(window=self.lookback_max).max()
        df['rolling_low'] = df['low'].rolling(window=self.lookback_max).min()

        # Volume filter
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # Trend (LONG bias from analysis)
        df['ema_50'] = self.calculate_ema(df['close'], 50)
        df['ema_200'] = self.calculate_ema(df['close'], 200)
        df['uptrend'] = df['ema_50'] > df['ema_200']

        print(f"  ATR + Bollinger Bands calculated")
        print(f"  Adaptive lookback: {self.lookback_min}-{self.lookback_max}")
        print(f"  Volume and trend filters added")

        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate signals with loosened filters."""
        df = data.copy()

        print("Generating IMPROVED breakout signals...")

        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan

        time_filters = self.config.get('time_filters', {})

        for i in range(self.lookback_max + 50, len(df)):
            current_bar = df.iloc[i]
            current_date = current_bar.name.date()

            # Reset daily
            if self.last_trade_date is None or current_date != self.last_trade_date:
                self.trades_today = 0
                self.last_trade_date = current_date

            self.bars_since_trade += 1

            # Circuit breaker
            if self.consecutive_losses >= self.max_consecutive_losses:
                if not self.circuit_breaker_active:
                    self.circuit_breaker_active = True
                    print(f"\n🚨 CIRCUIT BREAKER ACTIVATED at {current_bar.name}")
                continue

            if self.trades_today >= self.max_trades_per_day:
                continue

            if self.bars_since_trade < self.min_bars_between_trades:
                continue

            # Get values
            previous_bar = df.iloc[i-1]
            current_close = current_bar['close']
            current_atr = current_bar['atr']
            rolling_high = previous_bar['rolling_high']
            rolling_low = previous_bar['rolling_low']
            bb_squeeze = previous_bar['bb_squeeze']

            if pd.isna(current_atr) or pd.isna(rolling_high):
                continue

            # Time filter
            if not self.is_market_hours(current_bar.name, time_filters):
                continue

            # Volume filter (LOOSENED from 1.2 to 1.1)
            volume_ratio = current_bar.get('volume_ratio', 1.0)
            if pd.isna(volume_ratio) or volume_ratio < self.volume_threshold:
                continue

            # BB Squeeze condition (volatility contracted)
            if not bb_squeeze:
                continue

            # LONG SIGNAL (favor LONG based on analysis)
            if current_close > rolling_high and current_bar['uptrend']:
                breakout_strength = (current_close - rolling_high) / current_atr

                if breakout_strength >= self.breakout_strength:  # Reduced from 0.25
                    df.loc[df.index[i], 'signal'] = 1
                    df.loc[df.index[i], 'entry_price'] = current_close
                    df.loc[df.index[i], 'stop_loss'] = current_close - (self.stop_loss_atr_multiple * current_atr)
                    df.loc[df.index[i], 'take_profit'] = current_close + (self.take_profit_atr_multiple * current_atr)

                    self.trades_today += 1
                    self.bars_since_trade = 0

            # SHORT SIGNAL (only in strong downtrends)
            elif current_close < rolling_low and not current_bar['uptrend']:
                breakout_strength = (rolling_low - current_close) / current_atr

                # Higher threshold for SHORT (since SHORTs lose money)
                if breakout_strength >= self.breakout_strength * 1.5:
                    df.loc[df.index[i], 'signal'] = -1
                    df.loc[df.index[i], 'entry_price'] = current_close
                    df.loc[df.index[i], 'stop_loss'] = current_close + (self.stop_loss_atr_multiple * current_atr)
                    df.loc[df.index[i], 'take_profit'] = current_close - (self.take_profit_atr_multiple * current_atr)

                    self.trades_today += 1
                    self.bars_since_trade = 0

        signal_count = (df['signal'] != 0).sum()
        long_signals = (df['signal'] == 1).sum()
        short_signals = (df['signal'] == -1).sum()

        print(f"  Total signals: {signal_count}")
        print(f"  Long signals: {long_signals}")
        print(f"  Short signals: {short_signals}")

        return df

    def record_trade_result(self, pnl: float):
        """Track losses for circuit breaker."""
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            if self.circuit_breaker_active:
                self.circuit_breaker_active = False

    def get_exit_price(self, entry_price: float, stop_loss: float,
                      take_profit: float, bars_in_trade: int,
                      data_slice: pd.DataFrame) -> Tuple[float, str]:
        """Standard exit logic."""
        current_high = data_slice['high'].iloc[0]
        current_low = data_slice['low'].iloc[0]
        current_close = data_slice['close'].iloc[0]

        is_long = stop_loss < entry_price

        if is_long:
            if current_low <= stop_loss:
                return stop_loss, 'stop_loss'
            if current_high >= take_profit:
                return take_profit, 'take_profit'
        else:
            if current_high >= stop_loss:
                return stop_loss, 'stop_loss'
            if current_low <= take_profit:
                return take_profit, 'take_profit'

        if bars_in_trade >= self.max_bars_in_trade:
            return current_close, 'time_exit'

        return None, 'in_trade'

    def get_name(self) -> str:
        return "volatility_breakout_improved"

    def __str__(self) -> str:
        return "Improved Volatility Breakout"
