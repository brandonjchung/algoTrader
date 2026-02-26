"""
Breakout Fade Strategy
======================
Counter-trend strategy that fades breakouts instead of following them.

Logic:
- When price breaks ABOVE recent high on elevated volume -> SHORT (expect fade)
- When price breaks BELOW recent low on elevated volume -> LONG (expect bounce)

This is the inverse of trend following - we bet breakouts will reverse.
"""

import pandas as pd
import numpy as np


class BreakoutFadeStrategy:
    def __init__(self, config):
        self.config = config
        self.name = "breakout_fade"

        # Breakout detection
        self.breakout_period = config.get('breakout_period', 20)

        # Filters
        self.min_volume_ratio = config.get('min_volume_ratio', 1.5)
        self.atr_period = config.get('atr_period', 14)
        self.min_atr_for_entry = config.get('min_atr_for_entry', 2.0)
        self.max_atr_for_entry = config.get('max_atr_for_entry', 8.0)

        # Risk management
        self.stop_loss_atr_multiple = config.get('stop_loss_atr_multiple', 1.5)
        self.take_profit_atr_multiple = config.get('take_profit_atr_multiple', 2.0)
        self.use_trailing_stop = config.get('use_trailing_stop', False)

        # Time filters
        self.allowed_hours = config.get('allowed_hours', [14, 15, 16, 17, 18, 19, 20])
        self.max_trades_per_day = config.get('max_trades_per_day', 3)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 24)

        # State
        self.trades_today = 0
        self.last_trade_date = None

    def get_name(self):
        return self.name

    def calculate_indicators(self, data):
        df = data.copy()

        # ATR for volatility
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.atr_period).mean()

        # Breakout levels
        df['breakout_high'] = df['high'].rolling(self.breakout_period).max()
        df['breakout_low'] = df['low'].rolling(self.breakout_period).min()

        # Volume ratio
        df['volume_avg'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_avg']

        return df

    def generate_signals(self, data):
        df = self.calculate_indicators(data)
        df['signal'] = 0

        signals = {
            'total': 0,
            'long_fades': 0,
            'short_fades': 0,
            'skipped_atr': 0,
            'skipped_volume': 0,
            'skipped_time': 0,
        }

        for i in range(self.breakout_period + self.atr_period, len(df)):
            bar = df.iloc[i]
            prev_bar = df.iloc[i - 1]

            # Reset daily counter
            if self.last_trade_date is None or bar.name.date() != self.last_trade_date:
                self.trades_today = 0
                self.last_trade_date = bar.name.date()

            if self.trades_today >= self.max_trades_per_day:
                continue

            # Time filter
            current_hour = bar.name.hour
            if current_hour not in self.allowed_hours:
                signals['skipped_time'] += 1
                continue

            # ATR filter
            if bar['atr'] < self.min_atr_for_entry or bar['atr'] > self.max_atr_for_entry:
                signals['skipped_atr'] += 1
                continue

            # Volume filter
            if bar['volume_ratio'] < self.min_volume_ratio:
                signals['skipped_volume'] += 1
                continue

            # FADE LONG (buy the breakdown)
            if (prev_bar['low'] > prev_bar['breakout_low'] and
                bar['low'] <= bar['breakout_low']):
                df.at[df.index[i], 'signal'] = 1
                signals['long_fades'] += 1
                signals['total'] += 1
                self.trades_today += 1

            # FADE SHORT (sell the breakout)
            elif (prev_bar['high'] < prev_bar['breakout_high'] and
                  bar['high'] >= bar['breakout_high']):
                df.at[df.index[i], 'signal'] = -1
                signals['short_fades'] += 1
                signals['total'] += 1
                self.trades_today += 1

        print(f"Generating BREAKOUT FADE signals...")
        print(f"  Total signals: {signals['total']}")
        print(f"  Long fades (buy breakdown):  {signals['long_fades']}")
        print(f"  Short fades (sell breakout): {signals['short_fades']}")
        print(f"  Skipped (ATR):   {signals['skipped_atr']}")
        print(f"  Skipped (volume): {signals['skipped_volume']}")
        print(f"  Skipped (time):  {signals['skipped_time']}")

        return df

    def get_stop_loss(self, entry_price, direction, atr):
        stop_distance = self.stop_loss_atr_multiple * atr
        if direction == 1:  # LONG
            return entry_price - stop_distance
        else:  # SHORT
            return entry_price + stop_distance

    def get_take_profit(self, entry_price, direction, atr):
        profit_distance = self.take_profit_atr_multiple * atr
        if direction == 1:  # LONG
            return entry_price + profit_distance
        else:  # SHORT
            return entry_price - profit_distance

    def get_exit_price(self, entry_price, stop_loss, take_profit, bars_in_trade, data_slice):
        bar = data_slice.iloc[0]
        is_long = stop_loss < entry_price

        # Hard stop
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
