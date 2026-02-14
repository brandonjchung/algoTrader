"""
Mean Reversion Strategy using RSI
==================================

Strategy Logic:
- Identify oversold/overbought conditions using RSI
- Enter when price is extended from mean and likely to revert
- Exit when price returns to mean or hits profit target

Entry Rules:
- LONG: RSI < 30 (oversold) + price below 20-period EMA
- SHORT: RSI > 70 (overbought) + price above 20-period EMA

Exit Rules:
- Take Profit: RSI returns to 50 (neutral) OR 2.0x ATR profit
- Stop Loss: 1.5x ATR (tighter than breakout strategy)
- Time Exit: Maximum 30 bars in trade

This strategy works best in choppy/ranging markets (S&P 500 is mean-reverting 70% of the time)
"""

import pandas as pd
import numpy as np
from typing import Dict
from .base_strategy import BaseStrategy


class MeanReversionRSI(BaseStrategy):
    """Mean reversion strategy using RSI indicator."""

    def __init__(self, config: Dict):
        super().__init__(config)

        # Strategy parameters from config
        strategy_config = config.get('strategy', {})

        self.rsi_period = strategy_config.get('rsi_period', 14)
        self.rsi_oversold = strategy_config.get('rsi_oversold', 30)
        self.rsi_overbought = strategy_config.get('rsi_overbought', 70)
        self.rsi_neutral = strategy_config.get('rsi_neutral', 50)

        self.ema_period = strategy_config.get('ema_period', 20)
        self.atr_period = strategy_config.get('atr_period', 14)

        self.stop_loss_atr_multiple = strategy_config.get('stop_loss_atr_multiple', 1.5)
        self.take_profit_atr_multiple = strategy_config.get('take_profit_atr_multiple', 2.0)
        self.max_bars_in_trade = strategy_config.get('max_bars_in_trade', 30)

        self.max_trades_per_day = strategy_config.get('max_trades_per_day', 5)
        self.min_bars_between_trades = strategy_config.get('min_bars_between_trades', 3)

        # Track state
        self.trades_today = 0
        self.last_trade_date = None
        self.bars_since_trade = 999

        print(f"\nMean Reversion RSI Strategy Initialized:")
        print(f"  RSI Period: {self.rsi_period}")
        print(f"  RSI Oversold: {self.rsi_oversold}")
        print(f"  RSI Overbought: {self.rsi_overbought}")
        print(f"  EMA Period: {self.ema_period}")
        print(f"  Stop Loss: {self.stop_loss_atr_multiple}x ATR")
        print(f"  Take Profit: {self.take_profit_atr_multiple}x ATR")
        print(f"  Max Bars in Trade: {self.max_bars_in_trade}")

    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).

        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss over period
        """
        delta = data.diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators needed for the strategy."""
        df = data.copy()

        print("Calculating indicators for Mean Reversion strategy...")

        # RSI - Primary signal
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)

        # EMA - Mean/trend reference
        df['ema'] = self.calculate_ema(df['close'], self.ema_period)

        # ATR - Volatility for position sizing
        df['atr'] = self.calculate_atr(df, self.atr_period)

        # Distance from mean (in ATR units)
        df['distance_from_mean'] = (df['close'] - df['ema']) / df['atr']

        # Price above/below EMA
        df['above_ema'] = df['close'] > df['ema']
        df['below_ema'] = df['close'] < df['ema']

        print(f"  RSI calculated (period={self.rsi_period})")
        print(f"  EMA calculated (period={self.ema_period})")
        print(f"  ATR calculated (period={self.atr_period})")

        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals based on RSI mean reversion."""
        df = data.copy()

        print("Generating mean reversion signals...")

        # Initialize signal columns
        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan

        # Time filter config
        time_filters = self.config.get('time_filters', {})

        for i in range(self.ema_period + self.rsi_period, len(df)):
            current_bar = df.iloc[i]
            current_date = current_bar.name.date()

            # Reset daily trade counter
            if self.last_trade_date is None or current_date != self.last_trade_date:
                self.trades_today = 0
                self.last_trade_date = current_date

            # Increment bars since last trade
            self.bars_since_trade += 1

            # Skip if max trades per day reached
            if self.trades_today >= self.max_trades_per_day:
                continue

            # Skip if minimum bars between trades not met
            if self.bars_since_trade < self.min_bars_between_trades:
                continue

            # Get indicator values
            rsi = current_bar['rsi']
            current_close = current_bar['close']
            current_atr = current_bar['atr']
            ema = current_bar['ema']

            # Skip if indicators not ready
            if pd.isna(rsi) or pd.isna(current_atr) or pd.isna(ema):
                continue

            # Enforce time filters (avoid first/last minutes)
            if not self.is_market_hours(current_bar.name, time_filters):
                continue

            # LONG SIGNAL: RSI oversold + price below EMA (extended to downside)
            if rsi < self.rsi_oversold and current_close < ema:
                # Additional confirmation: price significantly below EMA
                distance_from_mean = current_bar['distance_from_mean']

                if distance_from_mean < -0.5:  # At least 0.5 ATR below mean
                    df.loc[df.index[i], 'signal'] = 1
                    df.loc[df.index[i], 'entry_price'] = current_close
                    df.loc[df.index[i], 'stop_loss'] = current_close - (self.stop_loss_atr_multiple * current_atr)
                    df.loc[df.index[i], 'take_profit'] = current_close + (self.take_profit_atr_multiple * current_atr)

                    self.trades_today += 1
                    self.bars_since_trade = 0

            # SHORT SIGNAL: RSI overbought + price above EMA (extended to upside)
            elif rsi > self.rsi_overbought and current_close > ema:
                distance_from_mean = current_bar['distance_from_mean']

                if distance_from_mean > 0.5:  # At least 0.5 ATR above mean
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

    def get_exit_price(self, entry_price: float, stop_loss: float,
                      take_profit: float, bars_in_trade: int,
                      data_slice: pd.DataFrame) -> tuple:
        """
        Determine exit price and reason for mean reversion strategy.

        Exits:
        1. RSI returns to neutral (mean reversion complete) - UNIQUE TO THIS STRATEGY
        2. Stop loss hit
        3. Take profit hit
        4. Time exit (max bars in trade)
        """
        current_bar = data_slice.iloc[0]
        current_high = current_bar['high']
        current_low = current_bar['low']
        current_close = current_bar['close']
        current_rsi = current_bar.get('rsi', 50)  # Default to neutral if not available

        is_long = stop_loss < entry_price

        # Check RSI neutral exit FIRST (mean reversion complete)
        if is_long and current_rsi >= self.rsi_neutral:
            return current_close, 'rsi_neutral'
        elif not is_long and current_rsi <= self.rsi_neutral:
            return current_close, 'rsi_neutral'

        # Standard exits
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

        # Time-based exit
        if bars_in_trade >= self.max_bars_in_trade:
            return current_close, 'time_exit'

        return None, 'in_trade'

    def get_name(self) -> str:
        """Return strategy name."""
        return "mean_reversion_rsi"

    def __str__(self) -> str:
        return "Mean Reversion RSI Strategy"
