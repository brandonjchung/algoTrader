"""
Base Strategy Class

This is the foundation for all trading strategies.
Every strategy inherits from this class and implements key methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    def __init__(self, config: Dict):
        """Initialize strategy with configuration parameters."""
        self.config = config
        self.name = config.get('name', 'base_strategy')
        self.data = None
        self.signals = None
        self.indicators = None
        
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators needed for the strategy."""
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals based on indicators."""
        pass
    
    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR) - measure of volatility."""
        high = data['high']
        low = data['low']
        close = data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average."""
        return data.rolling(window=period).mean()
    
    def is_market_hours(self, timestamp: pd.Timestamp, config: Dict) -> bool:
        """Check if timestamp is within allowed trading hours."""
        if not config.get('trade_only_rth', False):
            return True
            
        market_open = 9 * 60 + 30
        market_close = 16 * 60
        
        avoid_first = config.get('avoid_first_minutes', 0)
        avoid_last = config.get('avoid_last_minutes', 0)
        
        current_time = timestamp.hour * 60 + timestamp.minute
        
        return (market_open + avoid_first <= current_time <= market_close - avoid_last)
    
    def get_name(self) -> str:
        """Return strategy name."""
        return self.name
    
    def get_config(self) -> Dict:
        """Return strategy configuration."""
        return self.config
    
    def __str__(self) -> str:
        return f"{self.name} Strategy"
    
    def __repr__(self) -> str:
        return f"BaseStrategy(name='{self.name}')"
