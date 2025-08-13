"""
app/brokers/base.py

Abstract base class for broker integrations in the algo_trade_pro platform.
All specific broker modules (e.g. Zerodha, custom brokers) must inherit from this base.
Defines a common interface and contract for order placement, quotes, and order status.
"""

from typing import Dict, Optional, Any
from abc import ABC, abstractmethod

class BrokerBase(ABC):
    """
    Abstract base broker class.
    All brokers must implement this interface to ensure compatibility with
    the platform's execution and risk manager modules.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, access_token: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token

    @abstractmethod
    def place_order(self, symbol: str, side: str, quantity: int, price: float, order_type: str = "LIMIT") -> Dict:
        """
        Place an order with the broker.

        Args:
            symbol (str): Trading symbol (e.g., "RELIANCE", "TCS")
            side (str): "BUY" or "SELL"
            quantity (int): Number of shares/lots
            price (float): Limit or entry price
            order_type (str): Order type (default "LIMIT")

        Returns:
            dict: Order result (success, order_id, error, etc.)
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch latest quote data for a symbol.

        Args:
            symbol (str): Trading symbol

        Returns:
            dict or None: Quote data (ltp, bid, ask, OHLC, etc.)
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """
        Returns the live status of an order by id.

        Args:
            order_id (str): Broker order reference

        Returns:
            dict: Status info, e.g., {"status": "FILLED", "filled_price": 1421.1}
        """
        pass

    def cancel_order(self, order_id: str) -> Dict:
        """
        Optionally implement: Attempt to cancel a live order.

        Args:
            order_id (str): Broker order reference

        Returns:
            dict: {"success": True/False, "status": "...", "error": "..."}
        """
        # Default: Not implemented
        return {"success": False, "error": "Not implemented"}

    def authenticate(self):
        """
        Optionally implement: Authenticate or refresh tokens as needed.
        """
        pass
