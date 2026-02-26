"""
Volume Spike Reversal Strategy
===============================
Fades exhaustion moves marked by volume spikes + price overextension.

Logic:
- Volume spike (3x+ average) + close outside BB upper band -> SHORT
- Volume spike (3x+ average) + close outside BB lower band -> LONG

Rationale: Large volume often marks climax/exhaustion. Combined with
price overextension, expect mean reversion.
"""

import pandas as pd
import numpy as np


class VolumeSpikeReversalStrategy:
    def __init__(self, config):
        self.config = config
        self.name = "volume_spike_reversal"

        # Volume spike detection
        self.volume_period = config.get('volume_period', 20)
        self.volume_spike_threshold = config.get('volume_spike_threshold', 3.0)

        # Price overextension
        self.bb_period = config.get('bb_period', 20)
        self.bb_std_mult = config.get('bb_std_mult', 2.0)

        # ATR
        self.atr_period = config.get('atr_period', 14)
        self.min_atr_for_entry = config.get('min_atr_for_entry', 2.0)
        self.max_atr_for_entry = config.get('max_atr_for_entry', 8.0)

        # Risk management
        self.stop_loss_atr_multiple = config.get('stop_loss_atr_multiple', 1.5)
        self.take_profit_atr_multiple = config.get('take_profit_atr_multiple', 2.5)
        self.use_trailing_stop = config.get('use_trailing_stop', False)

        # Time filters
        self.allowed_hours = config.get('allowed_hours', [14, 15, 16, 17, 18, 19, 20, 21])
        self.max_trades_per_day = config.get('max_trades_per_day', 4)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 24)

        # State
        self.trades_today = 0
        self.last_trade_date = None

    def calculate_indicators(self, data):
        df = data.copy()

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(self.bb_period).mean()
        bb_std = df['close'].rolling(self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + self.bb_std_mult * bb_std
        df['bb_lower'] = df['bb_middle'] - self.bb_std_mult * bb_std

        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.atr_period).mean()

        # Volume ratio
        df['volume_avg'] = df['volume'].rolling(self.volume_period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_avg']

        return df

    def generate_signals(self, data):
        df = self.calculate_indicators(data)
        df['signal'] = 0

        signals = {
            'total': 0,
            'long_reversals': 0,
            'short_reversals': 0,
            'skipped_atr': 0,
            'skipped_volume': 0,
            'skipped_bb': 0,
            'skipped_time': 0,
        }

        for i in range(max(self.bb_period, self.volume_period, self.atr_period), len(df)):
            bar = df.iloc[i]

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

            # Volume spike required
            if bar['volume_ratio'] < self.volume_spike_threshold:
                signals['skipped_volume'] += 1
                continue

            # LONG: volume spike + close below lower BB (oversold exhaustion)
            if bar['close'] < bar['bb_lower']:
                df.at[df.index[i], 'signal'] = 1
                signals['long_reversals'] += 1
                signals['total'] += 1
                self.trades_today += 1

            # SHORT: volume spike + close above upper BB (overbought exhaustion)
            elif bar['close'] > bar['bb_upper']:
                df.at[df.index[i], 'signal'] = -1
                signals['short_reversals'] += 1
                signals['total'] += 1
                self.trades_today += 1

        print(f"Generating VOLUME SPIKE REVERSAL signals...")
        print(f"  Total signals: {signals['total']}")
        print(f"  Long reversals (buy climax sell):  {signals['long_reversals']}")
        print(f"  Short reversals (sell climax buy): {signals['short_reversals']}")
        print(f"  Skipped (ATR):    {signals['skipped_atr']}")
        print(f"  Skipped (volume): {signals['skipped_volume']}")
        print(f"  Skipped (time):   {signals['skipped_time']}")

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
