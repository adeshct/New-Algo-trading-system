import time
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

from app.queue.signal_queue import market_data_queue
from app.queue.trade_queue import trade_signal_queue
from app.strategies.base import BaseStrategy
from app.strategies.moving_average import MovingAverageStrategy
from app.strategies.rsi_strategy import RSIStrategy
from app.strategies.bollinger_bands import BollingerBandsStrategy
from app.strategies.cpr_startegy import CPRMetaMLStrategy
from app.services.logger import get_logger
from app.config.settings import get_settings
from app.strategies.registry import STRATEGY_REGISTRY
from app.services.utils import getTimeOfDay


logger = get_logger(__name__)
settings = get_settings()

def resample(df: pd.DataFrame):
    """
    Resample tick/second data to 5-min OHLCV bars.
    Assumes df index is pd.DatetimeIndex.
    """
    if df.empty:
        return df
    # df = pd.read_csv(r'C:\Users\SCGBS\Downloads\Data\Data\merged\niftyinfo.csv')
    # df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"],
    #                                 dayfirst=True, errors="coerce")
    # df.set_index("datetime", inplace=True)
    # df.sort_index(inplace=True)
    # logger.info(f"print(type(df.index): {type(df.index)}")
    # logger.info(f"print(df.index.dtype): {df.index.dtype}")
    # logger.info(f"print(df.index[:5]): {df.index[:5]}")
    # logger.info(f"The dataframe is as this: {df}")
    ohlcv = df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })
    return ohlcv.dropna()

class StrategyEngine:
    """Thread for executing trading strategies"""
    
    def __init__(self):
        self.running = False
        self.active_strategies: List[BaseStrategy] = []
        self.symbol_data: Dict[str, pd.DataFrame] = {}
        self._lock = threading.Lock()
        
        # Initialize default strategies
        self._initialize_strategies()

    
    def _initialize_strategies(self):
        """Initialize default trading strategies"""
        try:
            # Moving Average Strategy
            ma_strategy = MovingAverageStrategy(
                name="MA_CrossOver",
                short_window=5,
                long_window=20,
                symbols=['RELIANCE', 'TCS']
            )
            STRATEGY_REGISTRY[ma_strategy.name] = ma_strategy

            # RSI Strategy
            rsi_strategy = RSIStrategy(
                name="RSI_MeanReversion",
                rsi_period=14,
                oversold_threshold=30,
                overbought_threshold=70,
                symbols=['HDFCBANK', 'INFY']
            )
            STRATEGY_REGISTRY[rsi_strategy.name] = rsi_strategy

            # Bollinger Bands Strategy
            bb_strategy = BollingerBandsStrategy(
                name="BB_Breakout",
                period=20,
                std_dev=2,
                symbols=['ICICIBANK']
            )
            STRATEGY_REGISTRY[bb_strategy.name] = bb_strategy

             # CPR META ML Strategy
            cpr_strategy = CPRMetaMLStrategy(
                name = "CPR_Meta_ML"
            )
            STRATEGY_REGISTRY[cpr_strategy.name] = cpr_strategy
    
            # Assign all to active strategies
            self.active_strategies = [ma_strategy, rsi_strategy, bb_strategy, cpr_strategy]
            logger.info(f"Initialized {len(self.active_strategies)} strategies")

        except Exception as e:
            logger.error(f"Failed to initialize strategies: {e}")
            self.active_strategies = []
    
    def run(self):
        """Main strategy execution loop"""
        self.running = True
        logger.info("Strategy engine started")
        
        while self.running:
            try:
                self._process_market_data()
                self._execute_strategies()
                time.sleep(settings.STRATEGY_EXECUTION_INTERVAL)
            except Exception as e:
                logger.error(f"Error in strategy execution: {e}")
                time.sleep(300)  # Wait before retrying
        
        logger.info("Strategy engine stopped")
    
    
    
    def stop(self):
        """Stop strategy execution"""
        self.running = False
        logger.info("Strategy engine stopping...")
    
    def is_running(self) -> bool:
        """Check if strategy engine is running"""
        return self.running
    
    def _process_market_data(self):
        """Process incoming market data"""
        processed_count = 0
        
        # Process all available market data
        while not market_data_queue.empty():
            try:
                data = market_data_queue.get_nowait()
                logger.info(f"Market data: {data}")
                self._update_symbol_data(data)
                processed_count += 1
            except:
                break
        
        if processed_count > 0:
            logger.debug(f"Processed {processed_count} market data points")
    
    def _update_symbol_data(self, data: Dict):
        """Update symbol data for strategy analysis"""
        symbol = data['symbol']
        #logger.info(f"Symbol data in strategy engine: {data}")
        with self._lock:
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = pd.DataFrame()
            
            # Create new row
            new_row = pd.DataFrame([data])  
            #new_row['timestamp'] = pd.to_datetime(new_row['timestamp'])
            new_row = new_row.set_index('timestamp')
            
            # Append to existing data
            self.symbol_data[symbol] = pd.concat([self.symbol_data[symbol], new_row])
            
            # Keep only last 100 records
            # if len(self.symbol_data[symbol]) > 100:
            #     self.symbol_data[symbol] = self.symbol_data[symbol].tail(100)
    
   

    
    def _execute_strategies(self):
        """Execute all active strategies"""
        for strategy in self.active_strategies:
            try:
                if not strategy.is_enabled():
                    continue
                
                # Get required symbols for this strategy
                required_symbols = strategy.get_required_symbols()
                logger.info(f"Required Symbols: {required_symbols}")
                # Check if we have enough data
                symbol_data = {}
                now = datetime.now()
                if now.minute % 5 != 0:
                    mins_to_wait = 5 - now.minute % 5
                    logger.info("Sleeping for %d minutes", mins_to_wait)
                    time.sleep(timedelta.total_seconds(getTimeOfDay(hours=int(now.hour+1 if int(now.minute+mins_to_wait)==60 else now.hour), minutes=int(0 if int(now.minute+mins_to_wait)==60 else int(now.minute+mins_to_wait)),seconds=0) - now))

                if strategy.name!="CPR_Meta_ML" and now.minute % 5 == 0:
                    for symbol in required_symbols:
                        with self._lock:
                            if symbol in self.symbol_data and len(self.symbol_data[symbol]) >= strategy.min_data_points:
                                symbol_data[symbol] = self.symbol_data[symbol].copy()
                else:
                    for symbol in required_symbols:
                        with self._lock:
                            if symbol in self.symbol_data and len(self.symbol_data[symbol]) >= strategy.min_data_points:
                                df = self.symbol_data[symbol].copy()
                                logger.info(f"df before calling resample: {df}")
                                # Resample to 5-min bars
                                logger.info("Calling for resampling")
                                if not df.index.inferred_type == 'datetime64':
                                    df.index = pd.to_datetime(df.index)
                                df_5min = resample(df) #resample to 5 mins
                                logger.info(f"Resample done. This is the 5 mins data: {df_5min}")
                                # Pass only after market open and at least 2 bars are available
                                if len(df_5min) >= strategy.min_data_points:
                                    symbol_data[symbol] = df_5min

                # Execute strategy if we have enough data
                if len(symbol_data) == len(required_symbols):
                    signals = strategy.generate_signals(symbol_data)
                    
                    # Process generated signals
                    for signal in signals:
                        self._process_signal(signal, strategy.name)
                
            except Exception as e:
                logger.error(f"Error executing strategy {strategy.name}: {e}")
    
    def _process_signal(self, signal: Dict, strategy_name: str):
        """Process trading signal"""
        try:
            # Add metadata to signal
            signal['strategy'] = strategy_name
            signal['timestamp'] = datetime.now()
            signal['signal_id'] = f"{strategy_name}_{signal['symbol']}_{int(time.time())}"
            
            # Add to trade signal queue
            trade_signal_queue.put(signal)
            
            logger.info(f"Generated signal: {signal['action']} {signal['symbol']} Quanity is {signal['quantity']} "
                       f"at {signal['price']} (Strategy: {strategy_name})")
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a new strategy"""
        with self._lock:
            self.active_strategies.append(strategy)
            logger.info(f"Added strategy: {strategy.name}")
    
    def remove_strategy(self, strategy_name: str):
        """Remove a strategy"""
        with self._lock:
            self.active_strategies = [s for s in self.active_strategies if s.name != strategy_name]
            logger.info(f"Removed strategy: {strategy_name}")
    
    def get_active_strategies(self) -> List[str]:
        """Get list of active strategy names"""
        with self._lock:
            return [s.name for s in self.active_strategies]
    
    def enable_strategy(self, strategy_name: str):
        """Enable a strategy"""
        with self._lock:
            for strategy in self.active_strategies:
                if strategy.name == strategy_name:
                    strategy.enable()
                    logger.info(f"Enabled strategy: {strategy_name}")
                    return
    
    def disable_strategy(self, strategy_name: str):
        """Disable a strategy"""
        with self._lock:
            for strategy in self.active_strategies:
                if strategy.name == strategy_name:
                    strategy.disable()
                    logger.info(f"Disabled strategy: {strategy_name}")
                    return
    
    def get_strategy_performance(self, strategy_name: str) -> Dict:
        """Get performance metrics for a strategy"""
        with self._lock:
            for strategy in self.active_strategies:
                if strategy.name == strategy_name:
                    return strategy.get_performance_metrics()
        return {}

    