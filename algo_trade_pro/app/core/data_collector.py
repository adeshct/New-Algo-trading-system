import threading
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from app.queue.signal_queue import market_data_queue, websocket_queue
from app.services.logger import get_logger
from app.config.settings import get_settings
from app.brokers.base import BrokerBase

from app.services.websocket_collector import WebsocketCollector

logger = get_logger(__name__)
settings = get_settings()


class DataCollector:
    """Collects market data using websocket and feeds it to strategy engine."""

    def __init__(self, broker: BrokerBase):
        self.broker = broker
        self.is_running = False
        self.symbols = set()
        self.data_cache = {}
        self._lock = threading.Lock()

        self.token_map = {}
        self.subscribe_tokens = set()

        self.ws_collector = None
        
    def add_symbols(self, symbols):
        with self._lock:
            for sym in symbols:
                self.symbols.add(sym.upper())
                token = self.broker.get_instrument_token(sym)
                if token:
                    self.subscribe_tokens.add(token)
        logger.info(f"Added symbols: {symbols}")
        if hasattr(self.broker, "subscribe_tokens"):
            self.broker.subscribe_tokens = self.subscribe_tokens
            
    def remove_symbols(self, symbols):
        with self._lock:
            for symbol in symbols:
                sym = symbol.upper()
                self.symbols.discard(symbol.upper())
                token = self.broker.get_instrument_token(sym)
                if token and token in self.subscribe_tokens:
                    self.subscribe_tokens.discard(token)
                    self.token_map.pop(token, None)
        logger.info(f"Removed symbols from data collection: {symbols}")

    def run(self):
        """Start websocket collector and run indefinitely."""
        # if not self.subscribe_tokens:
        #     logger.warning("No symbols subscribed to collect.")
        #     return

        self.is_running = True
        logger.info("Starting DataCollector with websocket...")
        
        # Create an output queue where websocket events are put
        self.out_queue = websocket_queue
        self.ws_client = self.broker.create_ws_client(self.out_queue)

        # Thread to start WS connection
        threading.Thread(target=self.ws_client.connect, kwargs={"threaded": True}, daemon=True).start()
        logger.info("Threading started for WS_CLIENT")
        # Consume from websocket queue and route to market_data_queue
        while self.is_running:
            try:
                #logger.info("Inside Try")
                tick = self.out_queue.get(timeout=1)  # Wait for new ticks

                symbol = tick["symbol"]
                #logger.info(f"tick data: {tick}")
                with self._lock:
                    #logger.info("Inside lock")
                    if symbol not in self.data_cache:
                        self.data_cache[symbol] = []
                    self.data_cache[symbol].append(tick)
                    #logger.info("Halfway through lock")
                    if len(self.data_cache[symbol]) > 200:
                        self.data_cache[symbol] = self.data_cache[symbol][-200:]

                market_data_queue.put(tick)
                logger.debug(f"DataCollector pushed tick for {symbol} at {tick['timestamp']}")

            except Exception as e:
                # Timeout or other exception can be ignored/logged
                logger.error(f"Inside Exception: execept: {e}")
                continue

    def stop(self):
        self.is_running = False
        if self.ws_client:
            try: self.ws_client.close()
            except: pass
        logger.info("DataCollector stopping and websocket closed")

    def get_historical_data(self, symbol: str, periods: int = 100) -> pd.DataFrame:
        """Get cached historical data for a symbol."""
        with self._lock:
            if symbol not in self.data_cache:
                return pd.DataFrame()
            data = self.data_cache[symbol][-periods:]
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            return df

    def get_latest_price(self, symbol: str) -> float:
        with self._lock:
            if symbol not in self.data_cache or not self.data_cache[symbol]:
                return 0.0
            return self.data_cache[symbol][-1]['close']

    def is_running(self) -> bool:
        return self.is_running
