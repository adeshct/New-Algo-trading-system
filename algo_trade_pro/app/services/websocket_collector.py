# app/services/websocket_collector.py

import threading
from kiteconnect import KiteTicker

from app.services.logger import get_logger
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()

class WebsocketCollector:
    def __init__(self, api_key, access_token, tokens, out_queue):
        self.kws = KiteTicker(api_key, access_token)
        
        self.tokens = tokens
        self.out_queue = out_queue

        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close

    def start(self):
        t = threading.Thread(target=self.kws.connect, kwargs={'threaded': True})
        t.daemon = True
        t.start()

    def on_connect(self, ws, response):
        print("WebSocket connected.")
        ws.subscribe(self.tokens)

    def on_close(self, ws, code, reason):
        print("WebSocket closed:", reason)

    def on_ticks(self, ws, ticks):
        for tick in ticks:
            symbol = self.resolve_symbol(tick["instrument_token"])
            market_data = {
                'symbol': symbol,
                'timestamp': tick.get("timestamp"),
                'open': tick.get("ohlc", {}).get("open", tick["last_price"]),
                'high': tick.get("ohlc", {}).get("high", tick["last_price"]),
                'low': tick.get("ohlc", {}).get("low", tick["last_price"]),
                'close': tick["last_price"],
                'volume': tick.get("volume", 0),
                'ltp': tick["last_price"]
            }
            self.out_queue.put(market_data)

    def resolve_symbol(self, instrument_token):
        # You need a mapping from token <-> symbol
        # This could call a dict or your instrument dump
        return "NIFTY 50"

