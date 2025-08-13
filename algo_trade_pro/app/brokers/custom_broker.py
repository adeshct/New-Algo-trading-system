
import random
from datetime import datetime
from typing import Dict, Optional, Any
from app.brokers.base import BrokerBase
from app.services.logger import get_logger

logger = get_logger(__name__)


class CustomBroker(BrokerBase):
    """Mock broker implementation for testing and paper trading."""

    def __init__(self):
        super().__init__()
        self.order_book = {}
        self.position_book = {}
        self.current_prices = {
            "RELIANCE": 2450.0,
            "TCS": 3225.0,
            "INFY": 1450.0,
            "HDFC": 1610.0,
            "ICICIBANK": 880.0,
            "SBIN": 570.0,
            "ITC": 420.0,
            "HDFCBANK": 1520.0,
            "KOTAKBANK": 1750.0,
            "BAJFINANCE": 6800.0
        }
        logger.info("[CustomBroker] Initialized in paper trading mode")

    def place_order(self, symbol: str, side: str, quantity: int, price: float, order_type: str = "LIMIT") -> Dict:
        """Simulate order placement with realistic behavior."""
        try:
            order_id = f"SIM-{symbol[:3]}-{random.randint(10000, 99999)}"
            
            # Simulate market price movement
            market_price = self._get_simulated_price(symbol)
            
            # Determine if order gets filled based on order type and price
            filled = self._should_order_fill(order_type, side, price, market_price)
            
            filled_price = None
            status = "PENDING"
            
            if filled:
                # Add small slippage for market orders
                if order_type.upper() == "MARKET":
                    slippage = random.uniform(-0.002, 0.002)  # ±0.2%
                    filled_price = market_price * (1 + slippage)
                else:
                    filled_price = price * (1 + random.uniform(-0.001, 0.001))  # Small execution variance
                
                status = "FILLED"
                
                # Update position book
                self._update_position(symbol, side, quantity, filled_price)

            # Store order in order book
            self.order_book[order_id] = {
                "symbol": symbol,
                "side": side.upper(),
                "quantity": quantity,
                "price": price,
                "filled_price": filled_price,
                "order_type": order_type.upper(),
                "status": status,
                "timestamp": datetime.utcnow(),
                "filled_timestamp": datetime.utcnow() if filled else None
            }

            logger.info(f"[CustomBroker] Order {status}: {order_id} → {side} {quantity} {symbol} @ {filled_price or price:.2f}")
            return {"success": True, "order_id": order_id, "status": status, "filled_price": filled_price}

        except Exception as e:
            logger.error(f"[CustomBroker] Order placement failed: {e}")
            return {"success": False, "error": str(e)}

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Generate realistic quote data for paper trading."""
        try:
            base_price = self.current_prices.get(symbol.upper(), 1000.0)
            
            # Simulate price movement
            price_change = random.uniform(-0.02, 0.02)  # ±2%
            ltp = base_price * (1 + price_change)
            
            # Update stored price
            self.current_prices[symbol.upper()] = ltp

            return {
                "symbol": symbol,
                "ltp": round(ltp, 2),
                "open": round(base_price * 0.995, 2),
                "high": round(base_price * 1.025, 2),
                "low": round(base_price * 0.985, 2),
                "close": round(base_price, 2),
                "volume": random.randint(10000, 500000),
                "bid": round(ltp * 0.999, 2),
                "ask": round(ltp * 1.001, 2),
                "timestamp": datetime.utcnow()
            }

        except Exception as e:
            logger.error(f"[CustomBroker] Failed to generate quote for {symbol}: {e}")
            return None

    def get_order_status(self, order_id: str) -> Dict:
        """Return status of simulated order."""
        try:
            order = self.order_book.get(order_id)
            if not order:
                return {"status": "NOT_FOUND", "error": "Order not found"}

            return {
                "status": order["status"],
                "filled_price": order.get("filled_price"),
                "filled_quantity": order["quantity"] if order["status"] == "FILLED" else 0,
                "pending_quantity": 0 if order["status"] == "FILLED" else order["quantity"],
                "order_timestamp": order["timestamp"]
            }

        except Exception as e:
            logger.error(f"[CustomBroker] Failed to fetch order status: {e}")
            return {"status": "ERROR", "error": str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Simulate order cancellation."""
        try:
            if order_id not in self.order_book:
                return {"success": False, "error": "Order not found"}

            order = self.order_book[order_id]
            if order["status"] == "FILLED":
                return {"success": False, "error": "Cannot cancel filled order"}

            order["status"] = "CANCELLED"
            logger.info(f"[CustomBroker] Order cancelled: {order_id}")
            return {"success": True, "status": "CANCELLED"}

        except Exception as e:
            logger.error(f"[CustomBroker] Order cancellation failed: {e}")
            return {"success": False, "error": str(e)}

    def get_positions(self) -> Dict:
        """Get current simulated positions."""
        return {"success": True, "positions": list(self.position_book.values())}

    def get_holdings(self) -> Dict:
        """Get simulated holdings."""
        holdings = []
        for symbol, position in self.position_book.items():
            if position["quantity"] > 0:
                current_price = self.current_prices.get(symbol, position["avg_price"])
                holdings.append({
                    "symbol": symbol,
                    "quantity": position["quantity"],
                    "avg_price": position["avg_price"],
                    "current_price": current_price,
                    "pnl": (current_price - position["avg_price"]) * position["quantity"]
                })
        return {"success": True, "holdings": holdings}

    def _get_simulated_price(self, symbol: str) -> float:
        """Get current simulated price for symbol."""
        return self.current_prices.get(symbol.upper(), 1000.0)

    def _should_order_fill(self, order_type: str, side: str, price: float, market_price: float) -> bool:
        """Determine if order should be filled based on market conditions."""
        if order_type.upper() == "MARKET":
            return True  # Market orders always fill
        
        # Limit order logic
        if side.upper() == "BUY":
            return price >= market_price  # Buy limit fills if price >= market
        else:
            return price <= market_price  # Sell limit fills if price <= market

    def _update_position(self, symbol: str, side: str, quantity: int, price: float):
        """Update position book with new trade."""
        symbol = symbol.upper()
        
        if symbol not in self.position_book:
            self.position_book[symbol] = {"quantity": 0, "avg_price": 0.0, "total_value": 0.0}

        position = self.position_book[symbol]
        
        if side.upper() == "BUY":
            new_total_value = position["total_value"] + (quantity * price)
            new_quantity = position["quantity"] + quantity
            position["avg_price"] = new_total_value / new_quantity if new_quantity > 0 else 0
            position["quantity"] = new_quantity
            position["total_value"] = new_total_value
        else:  # SELL
            position["quantity"] -= quantity
            if position["quantity"] <= 0:
                position["quantity"] = 0
                position["avg_price"] = 0
                position["total_value"] = 0
            else:
                position["total_value"] = position["quantity"] * position["avg_price"]