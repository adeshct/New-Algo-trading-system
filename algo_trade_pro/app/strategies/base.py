"""
Base strategy class that all trading strategies must inherit from.
Provides common functionality and interface for strategy development.
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime
from app.services.logger import get_logger

logger = get_logger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, name: str, symbols: List[str], min_data_points: int = 20):
        self.name = name
        self.symbols = symbols
        self.min_data_points = min_data_points
        self.enabled = False
        self.signals_generated = 0
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.trade_pnls = []  # Track individual trade P&Ls
        self.max_drawdown = 0.0
        self.peak_pnl = 0.0

    @abstractmethod
    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on market data.
        
        Args:
            market_data: Dictionary mapping symbols to their OHLCV DataFrames
            
        Returns:
            List of signal dictionaries with keys: symbol, action, price, quantity
        """
        pass

    def is_enabled(self) -> bool:
        """Check if strategy is enabled."""
        return self.enabled

    def enable(self):
        """Enable the strategy."""
        self.enabled = True
        logger.info(f"Strategy {self.name} enabled")

    def disable(self):
        """Disable the strategy."""
        self.enabled = False
        logger.info(f"Strategy {self.name} disabled")

    def get_required_symbols(self) -> List[str]:
        """Get symbols required by this strategy."""
        return self.symbols

    def update_performance(self, trade_pnl: float):
        """Update strategy performance metrics."""
        self.trade_pnls.append(trade_pnl)
        self.total_pnl += trade_pnl
        self.trades_executed += 1
        
        if trade_pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
            
        # Update peak and drawdown
        if self.total_pnl > self.peak_pnl:
            self.peak_pnl = self.total_pnl
        
        current_drawdown = self.peak_pnl - self.total_pnl
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        total_trades = self.trades_executed
        win_rate = self.win_count / total_trades if total_trades > 0 else 0.0
        
        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = 0.0
        if len(self.trade_pnls) > 1:
            avg_return = sum(self.trade_pnls) / len(self.trade_pnls)
            returns_std = pd.Series(self.trade_pnls).std()
            sharpe_ratio = (avg_return / returns_std) if returns_std > 0 else 0.0
        
        return {
            "signals_generated": self.signals_generated,
            "trades_executed": total_trades,
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(win_rate, 4),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "avg_trade_pnl": round(self.total_pnl / total_trades, 2) if total_trades > 0 else 0.0
        }

    def _create_signal(self, symbol: str, action: str, price: float, quantity: int = 10, 
                      signal_type: str = "ENTRY", confidence: float = 1.0, metadata = None) -> Dict[str, Any]:
        """Create a standardized signal dictionary."""
        self.signals_generated += 1
        return {
            "symbol": symbol,
            "action": action.upper(),  # BUY or SELL
            "price": price,
            "quantity": quantity,
            "signal_type": signal_type,
            "confidence": confidence,
            "strategy": self.name,
            "timestamp": datetime.utcnow()
        }