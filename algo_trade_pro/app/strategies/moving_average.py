"""
Moving Average Crossover Strategy.
Generates signals when short-term MA crosses above/below long-term MA.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from app.strategies.base import BaseStrategy
from app.services.logger import get_logger

logger = get_logger(__name__)


class MovingAverageStrategy(BaseStrategy):
    """Moving Average Crossover trading strategy."""

    def __init__(self, name: str, short_window: int = 5, long_window: int = 20, 
                 symbols: List[str] = None, quantity: int = 10):
        symbols = symbols or ["RELIANCE", "TCS"]
        super().__init__(name, symbols, min_data_points=max(short_window, long_window) + 5)
        
        self.short_window = short_window
        self.long_window = long_window
        self.quantity = quantity
        self.last_signals = {}  # Track last signal per symbol to avoid duplicates

    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate moving average crossover signals."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in market_data:
                continue
                
            df = market_data[symbol]
            if len(df) < self.min_data_points:
                continue

            try:
                # Calculate moving averages
                df = df.copy()
                df['short_ma'] = df['close'].rolling(window=self.short_window).mean()
                df['long_ma'] = df['close'].rolling(window=self.long_window).mean()
                
                # Get latest values
                current = df.iloc[-1]
                previous = df.iloc[-2] if len(df) > 1 else current
                
                current_price = current['close']
                short_ma_current = current['short_ma']
                long_ma_current = current['long_ma']
                short_ma_prev = previous['short_ma']
                long_ma_prev = previous['long_ma']
                
                # Skip if MAs are not available
                if pd.isna(short_ma_current) or pd.isna(long_ma_current):
                    continue

                signal = None
                
                # Golden Cross (Bullish Signal)
                if (short_ma_prev <= long_ma_prev and short_ma_current > long_ma_current):
                    if self.last_signals.get(symbol) != "BUY":
                        signal = self._create_signal(
                            symbol=symbol,
                            action="BUY",
                            price=current_price,
                            quantity=self.quantity,
                            signal_type="GOLDEN_CROSS"
                        )
                        self.last_signals[symbol] = "BUY"
                        logger.info(f"[{self.name}] Golden Cross detected for {symbol} at {current_price:.2f}")

                # Death Cross (Bearish Signal)
                elif (short_ma_prev >= long_ma_prev and short_ma_current < long_ma_current):
                    if self.last_signals.get(symbol) != "SELL":
                        signal = self._create_signal(
                            symbol=symbol,
                            action="SELL",
                            price=current_price,
                            quantity=self.quantity,
                            signal_type="DEATH_CROSS"
                        )
                        self.last_signals[symbol] = "SELL"
                        logger.info(f"[{self.name}] Death Cross detected for {symbol} at {current_price:.2f}")

                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"[{self.name}] Error processing {symbol}: {e}")
                continue

        return signals

    def get_ma_values(self, symbol: str, market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Get current moving average values for a symbol."""
        if symbol not in market_data:
            return {}
            
        df = market_data[symbol]
        if len(df) < self.min_data_points:
            return {}
            
        df = df.copy()
        df['short_ma'] = df['close'].rolling(window=self.short_window).mean()
        df['long_ma'] = df['close'].rolling(window=self.long_window).mean()
        
        latest = df.iloc[-1]
        return {
            "short_ma": latest['short_ma'],
            "long_ma": latest['long_ma'],
            "price": latest['close']
        }