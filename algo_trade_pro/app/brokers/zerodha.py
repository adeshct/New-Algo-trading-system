"""
app/brokers/zerodha.py

Zerodha broker integration for AlgoTrade Pro platform.
Implements BrokerBase interface for execution, quotes, and order status.
"""

from typing import Optional, Dict, Any
from app.brokers.base import BrokerBase
from app.services.logger import get_logger
from app.services.kite import get_kite_client, get_ws_client
import yfinance as yf
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any

import random

try:
    from kiteconnect import KiteConnect
except ImportError:
    raise ImportError("Please install `kiteconnect` via pip install kiteconnect")

logger = get_logger(__name__)
logger.info("Logging initialized.")

class ZerodhaBroker(BrokerBase):
    """Zerodha Kite broker implementation"""

    # def __init__(
    #     self,
    #     api_key: Optional[str],
    #     api_secret: Optional[str],
    #     access_token: Optional[str],
    # ):
    #     super().__init__(api_key, api_secret, access_token)
    #     self.kite = self.get_kite_client()

    def __init__(self, kite_client: KiteConnect = None):
        super().__init__(None, None, None)
        self.kite = get_kite_client()
        self.kws = None
        self.instruments_df = pd.DataFrame()
        self.token_map = {}
        self.symbol_map = {}
        self._load_instruments()

    def _connect(self):
        """Create Kite client and set session"""
        
        if not self.api_key:
            raise ValueError("Zerodha API key is required")
        
        kite = KiteConnect(api_key=self.api_key)
        logger.info("Connecting to Zerodha broker with API key.")

        if self.access_token:
            kite.set_access_token(self.access_token)
        else:
            logger.warning("Zerodha access token missing.")
            raise ValueError("Access token is required for Zerodha session.")

        return kite

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "MARKET"
    ) -> Dict:
        """Place an order using Kite"""
        try:
            transaction_type = "BUY" if side.upper() == "BUY" else "SELL"

            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                #exchange=self._resolve_exchange(symbol),
                tradingsymbol=symbol.upper(),
                transaction_type=transaction_type,
                quantity=quantity,
                product=self.kite.PRODUCT_NRML,
                order_type=order_type.upper(),
                price=price if order_type.upper() == "MARKET" else None
            )

            logger.info(f"[Zerodha] Order placed: {order_id} for {side} {quantity} {symbol} @ {price}")
            return {"success": True, "order_id": order_id, "status": "PLACED"}

        except Exception as e:
            logger.error(f"[Zerodha] Order placement failed: {e}")
            return {"success": False, "error": str(e)}

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest quote for a tradingsymbol"""
        try:
            
            exchange = self._resolve_exchange(symbol)
            instrument_token = f"{exchange}:{symbol.upper()}"
            quote_data = self.kite.quote([instrument_token])[instrument_token]
            #logger.info(f'Quote data: {quote_data}')
            #For testing purpose
            #base_price = self.close.get(symbol.upper(), 1000.0)
            #price_change = random.uniform(-0.02, 0.02)  # ±2%
            #ltp = base_price * (1 + price_change)
            #self.close[symbol.upper()] = ltp 
            
            # return {
            #     "symbol": symbol,
            #     "ltp": round(ltp, 1),
            #     "open": round(base_price * 0.995, 1),
            #     "high": round(base_price * 1.025, 1),
            #     "low": round(base_price * 0.985, 1),
            #     "close": round(base_price, 1),
            #     "volume": random.randint(10000, 500000),
            #     "bid": round(ltp * 0.999, 1),
            #     "ask": round(ltp * 1.001, 1),
            #     "timestamp": datetime.utcnow()
            # }

            return {
                "symbol": symbol,
                "ltp": quote_data["last_price"],
                "open": quote_data["ohlc"]["open"],
                "high": quote_data["ohlc"]["high"],
                "low": quote_data["ohlc"]["low"],
                "close": quote_data["ohlc"]["close"],
                "volume": quote_data.get("volume_traded", 0),
                "bid": quote_data.get("depth", {}).get("buy", [{}])[0].get("price", 0),
                "ask": quote_data.get("depth", {}).get("sell", [{}])[0].get("price", 0),
                "timestamp": quote_data.get("last_trade_time")
            }

        except Exception as e:
            logger.error(f"[Zerodha] Failed to fetch quote for {symbol}: {e}")
            return None

    def get_order_status(self, order_id: str) -> Dict:
        """Check order lifetime status from order history"""
        try:
            order_history = self.kite.order_history(order_id)
            if not order_history:
                return {"status": "NOT_FOUND", "error": "Order not found"}

            latest_order = order_history[-1]
            return {
                "status": latest_order.get("status", "UNKNOWN"),
                "filled_price": latest_order.get("average_price"),
                "filled_quantity": latest_order.get("filled_quantity", 0),
                "pending_quantity": latest_order.get("pending_quantity", 0),
                "order_timestamp": latest_order.get("order_timestamp")
            }

        except Exception as e:
            logger.error(f"[Zerodha] Failed to fetch order status for {order_id}: {e}")
            return {"status": "ERROR", "error": str(e)}
        
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel order using Kite Connect API."""
        try:
            self.kite.cancel_order(order_id = order_id, variety = self.kite.VARIETY_REGULAR)
            logger.info(f"[Zerodha] Order cancelled: {order_id}")
            return {"success": True, "status": "CANCELLED"}

        except Exception as e:
            logger.error(f"[Zerodha] Order cancellation failed for {order_id}: {e}")
            return {"success": False, "error": str(e)}

    def _resolve_exchange(self, symbol: str) -> str:
        """Determine exchange for symbol (can be enhanced with instrument mapping)."""
        # Default to NSE for most stocks
        if symbol.upper() in ["NIFTY 50"]:
            return "NSE"
        elif symbol.upper() in ['SENSEX']:
            return "BSE"
        else: return "NSE"

    def get_positions(self) -> Dict:
        """Get current positions."""
        try:
            positions = self.kite.positions()["net"]
            result = []
            for pos in positions:
                # Adapt per your broker structure
                result.append({
                    "symbol": pos["tradingsymbol"],
                    "side": "BUY" if pos["quantity"] >= 0 else "SELL",
                    "quantity": abs(pos["quantity"]),
                    "buy_price": pos["buy_price"],
                    "current_price": pos["last_price"],  # must be fetched, if not present
                    "sell_price": pos["sell_price"],
                    "pnl": pos.get("pnl", 0.0)
                })
            return result
        except Exception as e:
            logger.error(f"[Zerodha] Failed to fetch positions: {e}")
            return {"success": False, "error": str(e)}

    def get_holdings(self) -> Dict:
        """Get current holdings."""
        try:
            holdings = self.kite.holdings()
            return {"success": True, "holdings": holdings}
        except Exception as e:
            logger.error(f"[Zerodha] Failed to fetch holdings: {e}")
            return {"success": False, "error": str(e)}
        
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        try:
            all_orders = self.kite.orders()
            return [
                order for order in all_orders
            if order["status"] in ("OPEN", "TRIGGER PENDING", "AMO REQ RECEIVED")
            ]
        except Exception as e:
            logger.error(f"[Zerodha] Failed to fetch pending orders: {e}")
            return []

    def _load_instruments(self):
        try:
            instruments = self.kite.instruments("NSE")
            logger.info("Instruments loaded")
            df = pd.DataFrame(instruments)
            self.instruments_df = df
            self.token_map = dict(zip(df.tradingsymbol.str.upper(), df.instrument_token))
            self.symbol_map = {v: k for k, v in self.token_map.items()}
        except Exception as e:
            logger.error(f"Failed loading instruments: {e}")

    
    def get_instrument_token(self, symbol: str) -> int:
        return self.token_map.get(symbol.upper())

    def resolve_symbol(self, token: int) -> str:
        return self.symbol_map.get(token, str(token))

    def create_ws_client(self, out_queue):
        from app.services.kite import get_ws_client
        nifty_token = self.get_instrument_token("NIFTY 50")
        self.subscribe_tokens = [nifty_token]
        def on_ticks(ws, ticks):
            for tick in ticks:
                if tick["instrument_token"] == nifty_token:
                    sym = self.resolve_symbol(tick["instrument_token"])
                    #logger.info("Inside ticks")
                    market_data = {
                        "symbol": sym,
                        "timestamp": tick.get("timestamp", datetime.now()),
                        "open": tick.get("ohlc", {}).get("open", tick["last_price"]),
                        "high": tick.get("ohlc", {}).get("high", tick["last_price"]),
                        "low": tick.get("ohlc", {}).get("low", tick["last_price"]),
                        "close": tick["last_price"],
                        "volume": tick.get("volume", 0),
                    }
                    #logger.info(f"Market Data for {sym} is fetched. Market data: {market_data}")
                    out_queue.put(market_data)

        def on_connect(ws, resp):
            logger.info("Zerodha WS connected, subscribing...")
            ws.subscribe(list(self.subscribe_tokens))
            ws.set_mode(ws.MODE_FULL, list(self.subscribe_tokens))

        def on_close(ws, code, reason):
            logger.warning(f"Zerodha WS closed: {reason}")

        self.kws = get_ws_client(on_ticks=on_ticks, on_connect=on_connect, on_close=on_close)
        return self.kws