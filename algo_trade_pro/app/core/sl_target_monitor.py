# Create: app/core/sl_target_monitor.py
import time
import threading
from typing import Dict, List
from datetime import datetime
from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus
from app.services.logger import get_logger
from app.brokers.base import BrokerBase

logger = get_logger(__name__)

class SLTargetMonitor:
    """Monitor underlying prices and place SL/Target orders for options trades."""
    
    def __init__(self, broker: BrokerBase, data_collector):
        self.broker = broker
        self.data_collector = data_collector
        self.running = False
        self.monitored_trades = {}  # Trade ID -> Trade object
        
    def run(self):
        """Main monitoring loop."""
        self.running = True
        logger.info("SL/Target monitor started")
        
        while self.running:
            try:
                self._update_monitored_trades()
                self._check_price_levels()
                time.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error in SL/Target monitor: {e}")
                time.sleep(5)
        
        logger.info("SL/Target monitor stopped")
    
    def stop(self):
        self.running = False
        
    def _update_monitored_trades(self):
        """Get active option trades that need monitoring."""
        with get_db_session() as db:
            active_trades = db.query(Trade).filter(
                Trade.status == TradeStatus.FILLED,
                Trade.stop_loss.isnot(None) | Trade.target.isnot(None),
                Trade.underlying_symbol.isnot(None)
            ).all()
            
            # Update monitored trades dictionary
            for trade in active_trades:
                self.monitored_trades[trade.id] = trade
                
    def _check_price_levels(self):
        """Check if underlying prices have crossed SL/Target levels."""
        for trade_id, trade in self.monitored_trades.items():
            try:
                # Get current underlying price
                underlying_price = self._get_underlying_price(trade.underlying_symbol)
                
                if underlying_price is None:
                    continue
                
                # Check for stop loss trigger
                if trade.stop_loss and underlying_price <= trade.stop_loss:
                    self._place_exit_order(trade, "STOP_LOSS", underlying_price)
                    
                # Check for target trigger  
                elif trade.target and underlying_price >= trade.target:
                    self._place_exit_order(trade, "TARGET", underlying_price)
                    
            except Exception as e:
                logger.error(f"Error checking trade {trade_id}: {e}")
    
    def _get_underlying_price(self, underlying_symbol: str) -> float:
        """Get current price of underlying asset."""
        try:
            # First try from data collector cache
            if hasattr(self.data_collector, 'get_latest_price'):
                price = self.data_collector.get_latest_price(underlying_symbol)
                if price:
                    return price
            
            # Fallback to broker quote
            quote = self.broker.get_quote(underlying_symbol)
            if quote and 'ltp' in quote:
                return quote['ltp']
                
        except Exception as e:
            logger.error(f"Failed to get price for {underlying_symbol}: {e}")
            
        return None
    
    def _place_exit_order(self, trade: Trade, exit_type: str, trigger_price: float):
        """Place exit order for the option trade."""
        try:
            # Place market sell order for the option
            order_result = self.broker.place_order(
                symbol=trade.symbol,  # Option symbol
                side="SELL" if trade.side.value == "BUY" else "BUY",
                quantity=trade.quantity,
                price=0,  # Market order
                order_type="MARKET"
            )
            
            if order_result.get('success'):
                # Update trade status
                with get_db_session() as db:
                    db_trade = db.query(Trade).filter(Trade.id == trade.id).first()
                    if db_trade:
                        db_trade.status = TradeStatus.EXITED
                        db_trade.exit_timestamp = datetime.utcnow()
                        db_trade.pending_sl_target = trigger_price
                        db.commit()
                
                # Remove from monitoring
                del self.monitored_trades[trade.id]
                
                logger.info(f"Placed {exit_type} order for {trade.symbol} at underlying price {trigger_price:.2f}")
                
            else:
                logger.error(f"Failed to place {exit_type} order for {trade.id}: {order_result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error placing {exit_type} order for {trade.id}: {e}")
