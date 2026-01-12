"""
Backtesting Engine

Simulates trading with realistic conditions including:
- Slippage and commissions
- Proper order execution
- Risk management rules
- Performance tracking
"""

from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.base_strategy import BaseStrategy


class Trade:
    """Represents a single trade from entry to exit."""
    
    def __init__(self, entry_time: datetime, entry_price: float, 
                 direction: int, size: int, stop_loss: float, 
                 take_profit: float, strategy_name: str):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.direction = direction
        self.size = size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.strategy_name = strategy_name
        
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = None
        self.pnl_pct = None
        self.bars_held = None
        self.mae = 0  # Maximum Adverse Excursion
        self.mfe = 0  # Maximum Favorable Excursion
        
    def update_excursion(self, current_high: float, current_low: float):
        """Update MAE and MFE based on current bar."""
        if self.direction == 1:  # Long
            current_loss = min(0, current_low - self.entry_price)
            current_profit = max(0, current_high - self.entry_price)
        else:  # Short
            current_loss = min(0, self.entry_price - current_high)
            current_profit = max(0, self.entry_price - current_low)
        
        self.mae = min(self.mae, current_loss)
        self.mfe = max(self.mfe, current_profit)
    
    def close(self, exit_time: datetime, exit_price: float, 
              exit_reason: str, point_value: float):
        """Close the trade and calculate final P&L."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        
        if self.direction == 1:
            points = exit_price - self.entry_price
        else:
            points = self.entry_price - exit_price
        
        self.pnl = points * point_value * self.size
        self.pnl_pct = (points / self.entry_price) * 100
        self.bars_held = (exit_time - self.entry_time).total_seconds() / 60 / 5
    
    def to_dict(self) -> Dict:
        """Convert trade to dictionary."""
        return {
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'direction': 'LONG' if self.direction == 1 else 'SHORT',
            'size': self.size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'exit_reason': self.exit_reason,
            'pnl': round(self.pnl, 2) if self.pnl else None,
            'pnl_pct': round(self.pnl_pct, 2) if self.pnl_pct else None,
            'bars_held': self.bars_held,
            'mae': round(self.mae, 2),
            'mfe': round(self.mfe, 2),
            'strategy': self.strategy_name
        }


class Backtester:
    """Main backtesting engine."""
    
    def __init__(self, strategy: BaseStrategy, data: pd.DataFrame, config: Dict):
        self.strategy = strategy
        self.data = data
        self.config = config
        
        self.initial_capital = config['trading']['initial_capital']
        self.point_value = config['contract']['point_value']
        self.tick_size = config['contract']['tick_size']
        self.tick_value = config['contract']['tick_value']
        
        self.commission_per_side = config['costs']['commission_per_side']
        self.slippage_ticks = config['costs']['slippage_ticks']
        
        self.max_positions = config['trading']['max_positions']
        self.max_daily_loss_pct = config['risk']['max_daily_loss_pct']
        
        self.equity = self.initial_capital
        self.peak_equity = self.initial_capital
        self.current_position = None
        self.trades = []
        self.equity_curve = []
        self.metrics = {}
        
    def calculate_slippage(self, entry_price: float, direction: int) -> float:
        """Calculate realistic slippage."""
        slippage_amount = self.slippage_ticks * self.tick_value
        
        if direction == 1:
            return entry_price + slippage_amount
        else:
            return entry_price - slippage_amount
    
    def calculate_commission(self, size: int) -> float:
        """Calculate round-trip commission."""
        return self.commission_per_side * 2 * size
    
    def check_daily_loss_limit(self, current_date: datetime) -> bool:
        """Check if max daily loss limit hit."""
        todays_trades = [t for t in self.trades if t.exit_time and t.exit_time.date() == current_date.date()]
        
        if not todays_trades:
            return False
        
        todays_pnl = sum(t.pnl for t in todays_trades)
        todays_pnl_pct = (todays_pnl / self.equity) * 100
        
        return todays_pnl_pct <= -self.max_daily_loss_pct
    
    def run(self) -> Dict:
        """Run the backtest simulation."""
        print(f"\nStarting backtest of {self.strategy.get_name()}...")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Data Range: {self.data.index[0]} to {self.data.index[-1]}")
        print(f"Total Bars: {len(self.data)}")
        
        print("\nCalculating indicators...")
        self.data = self.strategy.calculate_indicators(self.data)
        
        print("Generating signals...")
        self.data = self.strategy.generate_signals(self.data)
        
        print("\nRunning simulation...")
        bars_in_trade = 0
        
        for i in range(len(self.data)):
            current_bar = self.data.iloc[i]
            current_time = self.data.index[i]
            
            self.equity_curve.append({
                'time': current_time,
                'equity': self.equity,
                'drawdown_pct': ((self.equity - self.peak_equity) / self.peak_equity) * 100
            })
            
            if self.equity > self.peak_equity:
                self.peak_equity = self.equity
            
            if self.check_daily_loss_limit(current_time):
                continue
            
            # Manage open position
            if self.current_position is not None:
                bars_in_trade += 1
                
                self.current_position.update_excursion(
                    current_bar['high'],
                    current_bar['low']
                )
                
                exit_price, exit_reason = self.strategy.get_exit_price(
                    self.current_position.entry_price,
                    self.current_position.stop_loss,
                    self.current_position.take_profit,
                    bars_in_trade,
                    self.data.iloc[i:i+1]
                )
                
                if exit_price is not None:
                    exit_price = self.calculate_slippage(
                        exit_price,
                        -self.current_position.direction
                    )
                    
                    self.current_position.close(
                        current_time,
                        exit_price,
                        exit_reason,
                        self.point_value
                    )
                    
                    commission = self.calculate_commission(self.current_position.size)
                    self.equity += self.current_position.pnl - commission
                    
                    self.trades.append(self.current_position)
                    self.current_position = None
                    bars_in_trade = 0
                    
                    if len(self.trades) % 10 == 0:
                        print(f"  Completed {len(self.trades)} trades, Equity: ${self.equity:,.2f}")
            
            # Check for new entry
            elif current_bar['signal'] != 0:
                if self.current_position is None and self.equity > 0:
                    signal = current_bar['signal']
                    entry_price = current_bar['entry_price']
                    entry_price = self.calculate_slippage(entry_price, signal)
                    
                    self.current_position = Trade(
                        entry_time=current_time,
                        entry_price=entry_price,
                        direction=signal,
                        size=1,
                        stop_loss=current_bar['stop_loss'],
                        take_profit=current_bar['take_profit'],
                        strategy_name=self.strategy.get_name()
                    )
        
        # Close any remaining position
        if self.current_position is not None:
            final_bar = self.data.iloc[-1]
            self.current_position.close(
                self.data.index[-1],
                final_bar['close'],
                'end_of_data',
                self.point_value
            )
            self.equity += self.current_position.pnl - self.calculate_commission(1)
            self.trades.append(self.current_position)
        
        print("\nCalculating performance metrics...")
        self.calculate_metrics()
        
        print(f"\nBacktest Complete!")
        print(f"Total Trades: {len(self.trades)}")
        print(f"Final Equity: ${self.equity:,.2f}")
        print(f"Total Return: {((self.equity - self.initial_capital) / self.initial_capital * 100):.2f}%")
        
        return {
            'metrics': self.metrics,
            'trades': [t.to_dict() for t in self.trades],
            'equity_curve': self.equity_curve
        }
    
    def calculate_metrics(self):
        """Calculate comprehensive performance metrics."""
        if not self.trades:
            self.metrics = {'error': 'No trades executed'}
            return
        
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in self.trades)
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
        
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        equity_curve_df = pd.DataFrame(self.equity_curve)
        equity_curve_df['cummax'] = equity_curve_df['equity'].cummax()
        equity_curve_df['drawdown'] = equity_curve_df['equity'] - equity_curve_df['cummax']
        equity_curve_df['drawdown_pct'] = (equity_curve_df['drawdown'] / equity_curve_df['cummax']) * 100
        
        max_drawdown = equity_curve_df['drawdown'].min()
        max_drawdown_pct = equity_curve_df['drawdown_pct'].min()
        
        returns = equity_curve_df['equity'].pct_change().dropna()
        if len(returns) > 1:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        self.metrics = {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate_pct': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'total_return_pct': round((total_pnl / self.initial_capital) * 100, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_trade': round(avg_trade, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'final_equity': round(self.equity, 2),
            'expectancy': round(avg_trade, 2),
            'risk_reward_ratio': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0
        }
