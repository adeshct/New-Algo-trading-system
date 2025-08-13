"""
Bollinger Bands Strategy.
Generates signals based on price breakouts and mean reversion around Bollinger Bands.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from app.strategies.base import BaseStrategy
from app.services.logger import get_logger

logger = get_logger(__name__)


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands trading strategy for breakouts and mean reversion."""

    def __init__(self, name: str, period: int = 20, std_dev: float = 2.0,
                 symbols: List[str] = None, quantity: int = 10, strategy_type: str = "BREAKOUT"):
        symbols = symbols or ["ICICIBANK"]
        super().__init__(name, symbols, min_data_points=period + 5)
        
        self.period = period
        self.std_dev = std_dev
        self.quantity = quantity
        self.strategy_type = strategy_type.upper()  # BREAKOUT or REVERSION
        self.last_signals = {}

    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Generate Bollinger Bands-based signals."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in market_data:
                continue
                
            df = market_data[symbol]
            if len(df) < self.min_data_points:
                continue

            try:
                # Calculate Bollinger Bands
                df = df.copy()
                df['bb_middle'] = df['close'].rolling(window=self.period).mean()
                df['bb_std'] = df['close'].rolling(window=self.period).std()
                df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.std_dev)
                df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.std_dev)
                
                # Calculate Bollinger Band width for volatility assessment
                df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
                
                # Get latest values
                current = df.iloc[-1]
                previous = df.iloc[-2] if len(df) > 1 else current
                
                current_price = current['close']
                bb_upper = current['bb_upper']
                bb_lower = current['bb_lower']
                bb_middle = current['bb_middle']
                bb_width = current['bb_width']
                
                prev_price = previous['close']
                prev_bb_upper = previous['bb_upper']
                prev_bb_lower = previous['bb_lower']
                
                # Skip if Bollinger Bands are not available
                if pd.isna(bb_upper) or pd.isna(bb_lower):
                    continue

                signal = None
                
                if self.strategy_type == "BREAKOUT":
                    signal = self._generate_breakout_signal(
                        symbol, current_price, prev_price, bb_upper, bb_lower, 
                        prev_bb_upper, prev_bb_lower, bb_width
                    )
                else:  # REVERSION
                    signal = self._generate_reversion_signal(
                        symbol, current_price, bb_upper, bb_lower, bb_middle, bb_width
                    )

                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.error(f"[{self.name}] Error processing {symbol}: {e}")
                continue

        return signals

    def _generate_breakout_signal(self, symbol: str, current_price: float, prev_price: float,
                                bb_upper: float, bb_lower: float, prev_bb_upper: float,
                                prev_bb_lower: float, bb_width: float) -> Dict[str, Any]:
        """Generate breakout signals when price breaks through Bollinger Bands."""
        
        # Upper Breakout (Bullish)
        if prev_price <= prev_bb_upper and current_price > bb_upper:
            if self.last_signals.get(symbol) != "BUY" and bb_width > 0.02:  # Only in volatile conditions
                confidence = self._calculate_breakout_confidence(current_price, bb_upper, "upper")
                signal = self._create_signal(
                    symbol=symbol,
                    action="BUY",
                    price=current_price,
                    quantity=self.quantity,
                    signal_type="BB_UPPER_BREAKOUT",
                    confidence=confidence
                )
                self.last_signals[symbol] = "BUY"
                logger.info(f"[{self.name}] Upper breakout for {symbol} at {current_price:.2f} (BB Upper: {bb_upper:.2f})")
                return signal

        # Lower Breakout (Bearish)
        elif prev_price >= prev_bb_lower and current_price < bb_lower:
            if self.last_signals.get(symbol) != "SELL" and bb_width > 0.02:
                confidence = self._calculate_breakout_confidence(current_price, bb_lower, "lower")
                signal = self._create_signal(
                    symbol=symbol,
                    action="SELL",
                    price=current_price,
                    quantity=self.quantity,
                    signal_type="BB_LOWER_BREAKOUT",
                    confidence=confidence
                )
                self.last_signals[symbol] = "SELL"
                logger.info(f"[{self.name}] Lower breakout for {symbol} at {current_price:.2f} (BB Lower: {bb_lower:.2f})")
                return signal

        return None

    def _generate_reversion_signal(self, symbol: str, current_price: float, bb_upper: float,
                                 bb_lower: float, bb_middle: float, bb_width: float) -> Dict[str, Any]:
        """Generate mean reversion signals when price is near Bollinger Band extremes."""
        
        # Calculate position relative to bands
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
        
        # Buy signal when near lower band (oversold)
        if bb_position <= 0.1 and bb_width < 0.05:  # Near lower band in low volatility
            if self.last_signals.get(symbol) != "BUY":
                confidence = 1.0 - bb_position  # Higher confidence when closer to lower band
                signal = self._create_signal(
                    symbol=symbol,
                    action="BUY",
                    price=current_price,
                    quantity=self.quantity,
                    signal_type="BB_MEAN_REVERSION_BUY",
                    confidence=confidence
                )
                self.last_signals[symbol] = "BUY"
                logger.info(f"[{self.name}] Mean reversion buy for {symbol} at {current_price:.2f}")
                return signal

        # Sell signal when near upper band (overbought)
        elif bb_position >= 0.9 and bb_width < 0.05:
            if self.last_signals.get(symbol) != "SELL":
                confidence = bb_position  # Higher confidence when closer to upper band
                signal = self._create_signal(
                    symbol=symbol,
                    action="SELL",
                    price=current_price,
                    quantity=self.quantity,
                    signal_type="BB_MEAN_REVERSION_SELL",
                    confidence=confidence
                )
                self.last_signals[symbol] = "SELL"
                logger.info(f"[{self.name}] Mean reversion sell for {symbol} at {current_price:.2f}")
                return signal

        return None

    def _calculate_breakout_confidence(self, price: float, band_level: float, breakout_type: str) -> float:
        """Calculate confidence based on breakout strength."""
        if breakout_type == "upper":
            breakout_strength = (price - band_level) / band_level
        else:  # lower
            breakout_strength = (band_level - price) / band_level
        
        # Higher confidence for stronger breakouts
        confidence = min(1.0, max(0.5, breakout_strength * 10 + 0.7))
        return confidence

    def get_bollinger_values(self, symbol: str, market_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Get current Bollinger Bands values for a symbol."""
        if symbol not in market_data:
            return {}
            
        df = market_data[symbol]
        if len(df) < self.min_data_points:
            return {}
            
        df = df.copy()
        df['bb_middle'] = df['close'].rolling(window=self.period).mean()
        df['bb_std'] = df['close'].rolling(window=self.period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.std_dev)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.std_dev)
        
        latest = df.iloc[-1]
        bb_position = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
        
        return {
            "bb_upper": latest['bb_upper'],
            "bb_middle": latest['bb_middle'],
            "bb_lower": latest['bb_lower'],
            "price": latest['close'],
            "bb_position": bb_position,
            "near_upper": bb_position > 0.8,
            "near_lower": bb_position < 0.2
        }