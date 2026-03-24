"""
Trend Following Strategy - MES 5-min
=====================================
COMPLEMENT to mean_rev_quiet_filter.

Design principle: Trade the conditions mean reversion avoids.
  Mean rev works when: ATR 1.5-5.0, low volume, ranging
  This strategy targets:  ATR > 4.0,  high volume, trending

Core logic:
  - Entry: N-bar high/low breakout with momentum confirmation
  - Filter: ADX > threshold (trending market), volume spike (conviction)
  - ATR filter: require elevated volatility (real moves, not noise)
  - Stop: ATR-based (gives room for volatility)
  - Target: trailing ATR stop (let winners run with the trend)

Regime complement:
  When ATR < 5: mean_rev_quiet_filter.yaml is active
  When ATR > 4: this strategy is active
  (overlap zone 4-5 ATR: both may signal - use position sizing to manage)
"""

import pandas as pd
import numpy as np
from typing import Dict
import sys
sys.path.append('src')
from strategies.base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """
    Breakout/trend following strategy for MES futures.
    Designed to complement mean reversion - active when MR fails.
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # Breakout parameters
        self.breakout_period = config.get('breakout_period', 20)     # N-bar high/low lookback
        self.breakout_atr_buffer = config.get('breakout_atr_buffer', 0.25)  # ATR cushion above high

        # Momentum confirmation
        self.adx_period = config.get('adx_period', 14)
        self.adx_min_threshold = config.get('adx_min_threshold', 20)  # ADX > X = trending

        # Volume confirmation (opposite of MR - want high volume)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.2)   # require above-avg volume

        # ATR filter (require volatility - opposite of MR which avoids it)
        self.atr_period = config.get('atr_period', 14)
        self.min_atr_for_entry = config.get('min_atr_for_entry', 3.0)  # only when market is moving
        self.max_atr_for_entry = config.get('max_atr_for_entry', 12.0) # exclude extreme spikes

        # Momentum close confirmation: require close in top/bottom X% of bar range
        self.require_momentum_close = config.get('require_momentum_close', False)
        self.momentum_close_pct = config.get('momentum_close_pct', 0.75)  # top 25% for long, bottom 25% for short

        # Pullback entry mode: don't enter on breakout bar, wait for pullback
        self.use_pullback_entry = config.get('use_pullback_entry', False)
        self.pullback_lookback = config.get('pullback_lookback', 6)   # bars to wait for pullback after breakout
        self.pullback_pct = config.get('pullback_pct', 0.3)          # must retrace 30% of breakout move

        # Risk management
        self.stop_loss_atr_multiple = config.get('stop_loss_atr_multiple', 2.0)
        self.take_profit_atr_multiple = config.get('take_profit_atr_multiple', 4.0)
        self.use_trailing_stop = config.get('use_trailing_stop', True)
        self.trailing_stop_atr = config.get('trailing_stop_atr', 2.0)
        # Breakeven stop: once price moves breakeven_trigger_atr in your favor,
        # move hard stop to entry price (eliminates losers that bleed slowly).
        # Set breakeven_trigger_atr: 0 to disable.
        self.breakeven_trigger_atr = config.get('breakeven_trigger_atr', 0.0)

        # Time filters - trend moves happen at MORE active periods
        # (different from MR which uses quieter hours)
        self.allowed_hours = config.get('allowed_hours', [14, 15, 16, 17, 18, 19, 20])
        self.avoid_hours = config.get('avoid_hours', [])

        # Trade management
        self.max_trades_per_day = config.get('max_trades_per_day', 2)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 4)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 48)  # 4 hours max

        # State
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.trades_today = 0
        self.daily_pnl = 0
        self.last_trade_date = None
        self.trade_high_water_mark = {}
        self.trade_low_water_mark = {}

        # Pullback state: track recent breakouts waiting for pullback entry
        self.pending_breakouts = []  # list of {direction, breakout_price, breakout_level, atr, bar_idx}

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

        return adx, plus_di, minus_di

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate breakout and trend indicators."""
        df = data.copy()

        print("Calculating TREND FOLLOWING indicators...")

        # ATR for volatility measurement and stop sizing
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.atr_period).mean()

        # Breakout levels (N-bar high/low, shifted 1 so we don't include current bar)
        df['breakout_high'] = df['high'].rolling(window=self.breakout_period).max().shift(1)
        df['breakout_low'] = df['low'].rolling(window=self.breakout_period).min().shift(1)

        # ADX for trend strength
        df['adx'], df['plus_di'], df['minus_di'] = self.calculate_adx(df, self.adx_period)

        # Volume
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # Price momentum (rate of change)
        df['roc_5'] = df['close'].pct_change(5) * 100   # 5-bar ROC
        df['roc_20'] = df['close'].pct_change(20) * 100  # 20-bar ROC

        print(f"  ATR for volatility and stop sizing")
        print(f"  {self.breakout_period}-bar breakout levels")
        print(f"  ADX for trend strength (min: {self.adx_min_threshold})")
        print(f"  Volume confirmation (min ratio: {self.min_volume_ratio}x)")
        print(f"  Time filter: {self.allowed_hours}")

        return df

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trend following signals on breakouts with confirmation.

        Entry conditions:
          LONG:  close > N-bar high + buffer, ADX > threshold, volume spike, ATR in range
          SHORT: close < N-bar low  - buffer, ADX > threshold, volume spike, ATR in range
        """
        df = self.calculate_indicators(data)

        print("\nGenerating TREND FOLLOWING signals...")

        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan

        signals = {'long_breakout': 0, 'short_breakout': 0,
                   'pullback_long': 0, 'pullback_short': 0,
                   'skipped_adx': 0, 'skipped_volume': 0,
                   'skipped_atr': 0, 'skipped_time': 0,
                   'skipped_momentum_close': 0}

        for i in range(max(self.breakout_period + self.adx_period, 50), len(df)):
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
            high = bar['high']
            low = bar['low']
            atr = bar['atr']
            adx = bar['adx']
            volume_ratio = bar['volume_ratio']
            breakout_high = bar['breakout_high']
            breakout_low = bar['breakout_low']
            plus_di = bar['plus_di']
            minus_di = bar['minus_di']

            # Skip missing data
            if pd.isna(atr) or pd.isna(adx) or pd.isna(breakout_high):
                continue

            # ATR filter: require elevated but not extreme volatility
            if atr < self.min_atr_for_entry or atr > self.max_atr_for_entry:
                signals['skipped_atr'] += 1
                continue

            # ADX filter: require trending conditions
            if adx < self.adx_min_threshold:
                signals['skipped_adx'] += 1
                continue

            # Volume filter: require conviction (opposite of MR strategy)
            if pd.isna(volume_ratio) or volume_ratio < self.min_volume_ratio:
                signals['skipped_volume'] += 1
                continue

            # Entry buffer (small ATR fraction to avoid false breakouts)
            buffer = atr * self.breakout_atr_buffer
            bar_range = high - low

            # --- PULLBACK ENTRY MODE ---
            if self.use_pullback_entry:
                # Check for new breakouts to track (don't enter yet)
                if (close > breakout_high + buffer and plus_di > minus_di):
                    self.pending_breakouts.append({
                        'direction': 1,
                        'breakout_price': close,
                        'breakout_level': breakout_high,
                        'atr': atr,
                        'bar_idx': i,
                    })
                elif (close < breakout_low - buffer and minus_di > plus_di):
                    self.pending_breakouts.append({
                        'direction': -1,
                        'breakout_price': close,
                        'breakout_level': breakout_low,
                        'atr': atr,
                        'bar_idx': i,
                    })

                # Check pending breakouts for pullback entries
                still_pending = []
                for pb in self.pending_breakouts:
                    bars_since = i - pb['bar_idx']
                    if bars_since > self.pullback_lookback:
                        continue  # expired
                    if pb['direction'] == 1:  # long breakout
                        # Pullback: price retraced toward breakout level
                        retrace = pb['breakout_price'] - low
                        move = pb['breakout_price'] - pb['breakout_level']
                        if move > 0 and retrace / move >= self.pullback_pct and close > pb['breakout_level']:
                            # Pullback happened and price is still above breakout level
                            df.at[df.index[i], 'signal'] = 1
                            df.at[df.index[i], 'entry_price'] = close
                            df.at[df.index[i], 'stop_loss'] = close - (pb['atr'] * self.stop_loss_atr_multiple)
                            df.at[df.index[i], 'take_profit'] = close + (pb['atr'] * self.take_profit_atr_multiple)
                            signals['pullback_long'] += 1
                            self.trades_today += 1
                            continue  # consumed
                    else:  # short breakout
                        retrace = high - pb['breakout_price']
                        move = pb['breakout_level'] - pb['breakout_price']
                        if move > 0 and retrace / move >= self.pullback_pct and close < pb['breakout_level']:
                            df.at[df.index[i], 'signal'] = -1
                            df.at[df.index[i], 'entry_price'] = close
                            df.at[df.index[i], 'stop_loss'] = close + (pb['atr'] * self.stop_loss_atr_multiple)
                            df.at[df.index[i], 'take_profit'] = close - (pb['atr'] * self.take_profit_atr_multiple)
                            signals['pullback_short'] += 1
                            self.trades_today += 1
                            continue  # consumed
                    still_pending.append(pb)
                self.pending_breakouts = still_pending
                continue  # skip direct breakout entry when pullback mode is on

            # --- DIRECT BREAKOUT ENTRY (default) ---

            # Momentum close check: bar must close in top/bottom portion of its range
            if self.require_momentum_close and bar_range > 0:
                close_position = (close - low) / bar_range  # 0=closed at low, 1=closed at high

            # LONG: Price breaks above N-bar high with bullish momentum
            if (close > breakout_high + buffer and
                    plus_di > minus_di):  # bullish directional momentum

                # Momentum close: require close in top portion of bar
                if self.require_momentum_close and bar_range > 0:
                    close_position = (close - low) / bar_range
                    if close_position < self.momentum_close_pct:
                        signals['skipped_momentum_close'] += 1
                        continue  # bar wicked up but closed low = weak breakout

                df.at[df.index[i], 'signal'] = 1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close - (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = close + (atr * self.take_profit_atr_multiple)
                signals['long_breakout'] += 1
                self.trades_today += 1

            # SHORT: Price breaks below N-bar low with bearish momentum
            elif (close < breakout_low - buffer and
                  minus_di > plus_di):  # bearish directional momentum

                # Momentum close: require close in bottom portion of bar
                if self.require_momentum_close and bar_range > 0:
                    close_position = (close - low) / bar_range
                    if close_position > (1 - self.momentum_close_pct):
                        signals['skipped_momentum_close'] += 1
                        continue  # bar wicked down but closed high = weak breakout

                df.at[df.index[i], 'signal'] = -1
                df.at[df.index[i], 'entry_price'] = close
                df.at[df.index[i], 'stop_loss'] = close + (atr * self.stop_loss_atr_multiple)
                df.at[df.index[i], 'take_profit'] = close - (atr * self.take_profit_atr_multiple)
                signals['short_breakout'] += 1
                self.trades_today += 1

        total = (signals['long_breakout'] + signals['short_breakout'] +
                 signals['pullback_long'] + signals['pullback_short'])
        print(f"\n  Total signals: {total}")
        print(f"  Long breakouts:  {signals['long_breakout']}")
        print(f"  Short breakouts: {signals['short_breakout']}")
        if self.use_pullback_entry:
            print(f"  Pullback longs:  {signals['pullback_long']}")
            print(f"  Pullback shorts: {signals['pullback_short']}")
        if self.require_momentum_close:
            print(f"  Skipped (close): {signals['skipped_momentum_close']}")
        print(f"  Skipped (ATR):   {signals['skipped_atr']}")
        print(f"  Skipped (ADX):   {signals['skipped_adx']}")
        print(f"  Skipped (vol):   {signals['skipped_volume']}")
        print(f"  Skipped (time):  {signals['skipped_time']}")

        return df

    def get_exit_price(self, entry_price: float, stop_loss: float,
                       take_profit: float, bars_in_trade: int,
                       data_slice: pd.DataFrame) -> tuple:
        """
        Trend following exits: fixed TP, ATR trailing stop, or time exit.
        Let winners run longer than mean reversion (trend continuation expected).
        """
        bar = data_slice.iloc[0]
        current_high = bar['high']
        current_low = bar['low']
        current_close = bar['close']
        current_atr = bar.get('atr', 0)

        is_long = stop_loss < entry_price
        trade_id = entry_price

        # Trailing stop logic
        if self.use_trailing_stop and current_atr > 0:
            if trade_id not in self.trade_high_water_mark:
                self.trade_high_water_mark[trade_id] = current_high if is_long else entry_price
                self.trade_low_water_mark[trade_id] = entry_price if is_long else current_low

            if is_long:
                self.trade_high_water_mark[trade_id] = max(
                    self.trade_high_water_mark[trade_id], current_high)
                trail = self.trade_high_water_mark[trade_id] - (self.trailing_stop_atr * current_atr)
                # Use trailing stop once it's above entry (i.e., locking in profit)
                if trail > entry_price and current_low <= trail:
                    del self.trade_high_water_mark[trade_id]
                    return trail, 'trailing_stop'
            else:
                self.trade_low_water_mark[trade_id] = min(
                    self.trade_low_water_mark[trade_id], current_low)
                trail = self.trade_low_water_mark[trade_id] + (self.trailing_stop_atr * current_atr)
                if trail < entry_price and current_high >= trail:
                    del self.trade_low_water_mark[trade_id]
                    return trail, 'trailing_stop'

        # Breakeven stop: once price moves breakeven_trigger_atr in our favor,
        # promote the hard stop to entry price so we can't lose on this trade.
        if self.breakeven_trigger_atr > 0 and current_atr > 0:
            trigger = self.breakeven_trigger_atr * current_atr
            if is_long and current_high >= entry_price + trigger:
                stop_loss = max(stop_loss, entry_price)
            elif not is_long and current_low <= entry_price - trigger:
                stop_loss = min(stop_loss, entry_price)

        # Hard stop loss
        if is_long and current_low <= stop_loss:
            self._cleanup_watermarks(trade_id)
            return stop_loss, 'stop_loss'
        elif not is_long and current_high >= stop_loss:
            self._cleanup_watermarks(trade_id)
            return stop_loss, 'stop_loss'

        # Fixed take profit
        if is_long and current_high >= take_profit:
            self._cleanup_watermarks(trade_id)
            return take_profit, 'take_profit'
        elif not is_long and current_low <= take_profit:
            self._cleanup_watermarks(trade_id)
            return take_profit, 'take_profit'

        # Time exit (shorter than MR - trends can reverse)
        if bars_in_trade >= self.config.get('max_bars_in_trade', 48):
            self._cleanup_watermarks(trade_id)
            return current_close, 'time_exit'

        return None, None

    def _cleanup_watermarks(self, trade_id):
        self.trade_high_water_mark.pop(trade_id, None)
        self.trade_low_water_mark.pop(trade_id, None)

    def record_trade_result(self, pnl: float):
        """Track consecutive losses for circuit breaker."""
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            self.circuit_breaker_active = False
