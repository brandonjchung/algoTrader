"""
Volatility Breakout Strategy

Strategy Logic:
1. Wait for volatility to contract (ATR below recent average)
2. When price breaks above recent high or below recent low, enter
3. Use ATR-based stops and targets
4. Exit on target, stop, or time-based rule

Why This Can Work:
- Markets alternate between consolidation and trending
- Breakouts after consolidation often have follow-through
- ATR-based stops adapt to market conditions
"""

from typing import Dict, Tuple
import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy


class VolatilityBreakoutStrategy(BaseStrategy):
    """Volatility Breakout Strategy for MES futures."""
    
    def __init__(self, config: Dict):
        """Initialize strategy with parameters from config."""
        super().__init__(config)
        
        # Extract strategy-specific parameters
        self.lookback_period = config.get('lookback_period', 20)
        self.atr_period = config.get('atr_period', 14)
        self.vol_threshold = config.get('volatility_contraction_threshold', 0.7)
        self.stop_loss_mult = config.get('stop_loss_atr_multiple', 2.0)
        self.take_profit_mult = config.get('take_profit_atr_multiple', 3.0)
        self.max_bars_in_trade = config.get('max_bars_in_trade', 50)
        
        # Trading rules
        self.max_trades_per_day = config.get('max_trades_per_day', 3)
        self.min_bars_between_trades = config.get('min_bars_between_trades', 5)
        
        # Track state
        self.trades_today = 0
        self.bars_since_trade = 999
        self.current_date = None
        
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators needed for the strategy."""
        df = data.copy()
        
        # Calculate ATR (current volatility)
        df['atr'] = self.calculate_atr(df, self.atr_period)
        
        # Calculate average ATR over lookback period
        df['atr_ma'] = df['atr'].rolling(window=self.lookback_period).mean()
        
        # Find recent highs and lows (breakout levels)
        df['rolling_high'] = df['high'].rolling(window=self.lookback_period).max()
        df['rolling_low'] = df['low'].rolling(window=self.lookback_period).min()
        
        # Is volatility contracted?
        df['is_contracted'] = df['atr'] < (self.vol_threshold * df['atr_ma'])
        
        # Calculate range
        df['range'] = df['high'] - df['low']
        
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals based on volatility breakout logic."""
        df = data.copy()
        
        # Initialize signal columns
        df['signal'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        
        # Need sufficient data for indicators
        min_required_bars = max(self.lookback_period, self.atr_period) + 10
        
        for i in range(min_required_bars, len(df)):
            current_bar = df.iloc[i]
            previous_bar = df.iloc[i-1]
            
            # Reset trade count at start of new day
            if self.current_date != current_bar.name.date():
                self.current_date = current_bar.name.date()
                self.trades_today = 0
            
            self.bars_since_trade += 1
            
            # Skip if we've hit max trades or not enough time since last trade
            if self.trades_today >= self.max_trades_per_day:
                continue
            if self.bars_since_trade < self.min_bars_between_trades:
                continue
            
            # Get indicator values
            is_contracted = current_bar['is_contracted']
            rolling_high = previous_bar['rolling_high']
            rolling_low = previous_bar['rolling_low']
            current_close = current_bar['close']
            current_atr = current_bar['atr']
            
            # Skip if indicators not ready
            if pd.isna(current_atr) or pd.isna(rolling_high):
                continue
            
            # LONG SIGNAL: Volatility contracted + breakout above high
            if is_contracted and current_close > rolling_high:
                df.loc[df.index[i], 'signal'] = 1
                df.loc[df.index[i], 'entry_price'] = rolling_high
                df.loc[df.index[i], 'stop_loss'] = rolling_high - (self.stop_loss_mult * current_atr)
                df.loc[df.index[i], 'take_profit'] = rolling_high + (self.take_profit_mult * current_atr)
                
                self.trades_today += 1
                self.bars_since_trade = 0
            
            # SHORT SIGNAL: Volatility contracted + breakout below low
            elif is_contracted and current_close < rolling_low:
                df.loc[df.index[i], 'signal'] = -1
                df.loc[df.index[i], 'entry_price'] = rolling_low
                df.loc[df.index[i], 'stop_loss'] = rolling_low + (self.stop_loss_mult * current_atr)
                df.loc[df.index[i], 'take_profit'] = rolling_low - (self.take_profit_mult * current_atr)
                
                self.trades_today += 1
                self.bars_since_trade = 0
        
        return df
    
    def get_exit_price(self, entry_price: float, stop_loss: float, 
                      take_profit: float, bars_in_trade: int,
                      data_slice: pd.DataFrame) -> Tuple[float, str]:
        """Determine exit price and reason based on market action."""
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
    
    def __str__(self) -> str:
        return (f"Volatility Breakout Strategy\n"
                f"  Lookback: {self.lookback_period} bars\n"
                f"  ATR Period: {self.atr_period}\n"
                f"  Vol Threshold: {self.vol_threshold}\n"
                f"  Stop Loss: {self.stop_loss_mult}x ATR\n"
                f"  Take Profit: {self.take_profit_mult}x ATR")
