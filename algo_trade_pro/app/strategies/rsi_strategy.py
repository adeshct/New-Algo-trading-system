"""
RSI Mean Reversion Strategy.
Generates buy signals when RSI is oversold and sell signals when overbought.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from app.strategies.base import BaseStrategy
from app.services.logger import get_logger

logger = get_logger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI Mean Reversion trading strategy."""

    def __init__(self, name: str, rsi_period: int = 14, oversold_threshold: int = 30,
                 overbought_threshold: int = 70, symbols: List[str] = None, quantity: int = 10):
        symbols = symbols or ["HDFC", "INFY"]
        super().__init__(name, symbols, min_data_points=rsi_period + 5)
        
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.quantity = quantity
        self.last_signals = {}

    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate RSI-based mean reversion signals."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in market_data:
                continue
                
            df = market_data[symbol]
            if len(df) < self.min_data_points:
                continue

            try:
                # Calculate RSI
                df = df.copy()
                rsi_values = self._calculate_rsi(df['close'], self.rsi_period)
                df['rsi'] = rsi_values
                
                # Get latest values
                current = df.iloc[-1]
                previous = df.iloc[-2] if len(df) > 1 else current
                
                current_price = current['close']
                current_rsi = current['rsi']
                prev_rsi = previous['rsi']
                
                # Skip if RSI is not available
                if pd.isna(current_rsi) or pd.isna(prev_rsi):
                    continue

                signal = None
                
                # Oversold Bounce Signal (Buy)
                if (prev_rsi <= self.oversold_threshold and current_rsi > self.oversold_threshold):
                    if self.last_signals.get(symbol) != "BUY":
                        confidence = self._calculate_confidence(current_rsi, "oversold")
                        signal = self._create_signal(
                            symbol=symbol,
                            action="BUY",
                            price=current_price,
                            quantity=self.quantity,
                            signal_type="OVERSOLD_BOUNCE",
                            confidence=confidence
                        )
                        self.last_signals[symbol] = "BUY"
                        logger.info(f"[{self.name}] Oversold bounce for {symbol} at {current_price:.2f} (RSI: {current_rsi:.1f})")

                # Overbought Reversal Signal (Sell)
                elif (prev_rsi >= self.overbought_threshold and current_rsi < self.overbought_threshold):
                    if self.last_signals.get(symbol) != "SELL":
                        confidence = self._calculate_confidence(current_rsi, "overbought")
                        signal = self._create_signal(
                            symbol=symbol,
                            action="SELL",
                            price=current_price,
                            quantity=self.quantity,
                            signal_type="OVERBOUGHT_REVERSAL",
                            confidence=confidence
                        )
                        self.last_signals[symbol] = "SELL"
                        logger.info(f"[{self.name}] Overbought reversal for {symbol} at {current_price:.2f} (RSI: {current_rsi:.1f})")

                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"[{self.name}] Error processing {symbol}: {e}")
                continue

        return signals

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI (Relative Strength Index)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_confidence(self, rsi_value: float, signal_type: str) -> float:
        """Calculate signal confidence based on RSI extremity."""
        if signal_type == "oversold":
            # More confidence for lower RSI values
            confidence = max(0.5, min(1.0, (30 - rsi_value) / 20 + 0.5))
        else:  # overbought
            # More confidence for higher RSI values
            confidence = max(0.5, min(1.0, (rsi_value - 70) / 20 + 0.5))
        
        return confidence

    def get_rsi_values(self, symbol: str, market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Get current RSI values for a symbol."""
        if symbol not in market_data:
            return {}
            
        df = market_data[symbol]
        if len(df) < self.min_data_points:
            return {}
            
        df = df.copy()
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        
        latest = df.iloc[-1]
        return {
            "rsi": latest['rsi'],
            "price": latest['close'],
            "is_oversold": latest['rsi'] < self.oversold_threshold,
            "is_overbought": latest['rsi'] > self.overbought_threshold
        }