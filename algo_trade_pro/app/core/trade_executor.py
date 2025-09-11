import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from app.queue.trade_queue import trade_signal_queue
from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus, TradeSide
from app.brokers.base import BrokerBase
from app.services.logger import get_logger
from app.config.settings import get_settings
from app.strategies.registry import STRATEGY_REGISTRY
from app.brokers.zerodha import ZerodhaBroker


logger = get_logger(__name__)
settings = get_settings()

class TradeExecutor:
    """Executes trading signals and manages order lifecycle."""

    def __init__(self, broker: BrokerBase):
        self.broker = broker
        self.running = False
        self.pending_orders = {}  # order_id (str) -> trade_id (str)
        self.active_sl_target_orders = {}
        self._lock = threading.Lock()

    def run(self):
        """Main trade execution loop."""
        self.running = True
        logger.info("Trade executor started")
        while self.running:
            try:
                self._process_signals()
                self._check_pending_orders()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in trade execution: {e}")
                time.sleep(5)
        logger.info("Trade executor stopped")

    def stop(self):
        self.running = False
        logger.info("Trade executor stopping...")

    def _process_signals(self):
        """Process pending trading signals from the queue."""
        signals_processed = 0
        while not trade_signal_queue.empty():
            try:
                signal = trade_signal_queue.get_nowait()
                self._execute_signal(signal)
                signals_processed += 1
            except Exception as e:
                logger.exception(f"Error processing trade signal: {e}")
                break
        if signals_processed > 0:
            logger.debug(f"Processed {signals_processed} trading signals")

    def _execute_signal(self, signal: Dict[str, Any]):
        """Execute a single trading signal."""
        try:
            symbol = signal['symbol']
            action = signal['action']
            price = signal['price']
            quantity = signal.get('quantity', 10)
            strategy = signal.get('strategy', 'Unknown')

            trade_id = f"{symbol}_{action}_{int(time.time())}_{threading.get_ident()}"
            side = TradeSide.BUY if action == "BUY" else TradeSide.SELL
            metadata = signal.get('metadata', {})
            # 1. Create Trade record (insert into DB!)
            with get_db_session() as db:
                trade = Trade(
                    id=trade_id,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    status=TradeStatus.PENDING,
                    strategy=strategy,
                    timestamp=datetime.utcnow(),
                    stop_loss=metadata.get('stoploss'),
                    target=metadata.get('target'),
                    underlying_symbol=metadata.get('underlying_symbol'),
                )
                db.add(trade)
                db.commit()
                # Optionally: db.refresh(trade) if you need fields auto-filled right now

            # 2. Place order with broker
            order_result = self.broker.place_order(
                symbol=symbol,
                side=action,
                quantity=quantity,
                price=price,
                order_type="MARKET"
            )
            logger.info(f"Broker returned: {order_result}")

            if order_result.get('success'):
                broker_order_id = order_result.get('order_id')
                logger.info(f"Order is success: {broker_order_id}")
                # 3. Update the trade row with the broker order id
                with get_db_session() as db:
                    db.query(Trade).filter(Trade.id == trade_id).update({
                        "order_id": broker_order_id
                    })
                    db.commit()
                
                metadata = signal.get('metadata', {})
                if metadata.get('stoploss') or metadata.get('target'):
                    self._schedule_sl_target_placement(trade_id, metadata, symbol, quantity, action)

                # 4. If FILLED immediately, handle; otherwise, add to pending
                if order_result.get('status') == 'FILLED':
                    logger.info(f"Order is filled: {broker_order_id}")
                    filled_price = order_result.get('filled_price', price)
                    self._handle_fill(trade_id, filled_price)
                else:
                    with self._lock:
                        self.pending_orders[broker_order_id] = trade_id
                logger.info(f"Order Placed: action={action}, quantity={quantity}, symbol={symbol}, price={price}, broker_order_id={broker_order_id}")
            else:
                error_msg = order_result.get('error', 'Unknown error')
                # 5. Mark as rejected in the DB
                with get_db_session() as db:
                    db.query(Trade).filter(Trade.id == trade_id).update({
                        "status": TradeStatus.REJECTED.value,
                        "error_message": error_msg
                    })
                    db.commit()
                logger.error(f"Order failed: {action} {quantity} {symbol} @ {price:.2f} - {error_msg}")

        except Exception as e:
            logger.exception(f"Error executing signal: {e}")

    def _schedule_sl_target_placement(self, trade_id: str, metadata: dict, symbol: str, quantity: int, action: str):
        """Schedule SL/Target orders to be placed after main order is filled"""
        with self._lock:
            self.pending_sl_target = self.pending_sl_target or {}
            self.pending_sl_target[trade_id] = {
                'symbol': symbol,
                'quantity': quantity,
                'action': action,
                'stoploss': metadata.get('stoploss'),
                'target': metadata.get('target'),
                'timestamp': datetime.utcnow()
            }

    def _place_sl_target_orders(self, trade_id: str, sl_target_info: dict):
        """Place SL and Target orders after main position is filled"""
        try:
            symbol = sl_target_info['symbol']
            quantity = sl_target_info['quantity']
            original_action = sl_target_info['action']
            
            # Determine exit side (opposite of entry)
            exit_side = "SELL" if original_action == "BUY" else "BUY"
            
            target_order_id = None
            stoploss_order_id = None
            
            # Place Target Order
            if sl_target_info.get('target'):
                target_result = self.broker.place_order(
                    symbol=symbol,
                    side=exit_side,
                    quantity=quantity,
                    price=sl_target_info['target'],
                    order_type="LIMIT"
                )
                if target_result.get('success'):
                    target_order_id = target_result.get('order_id')
                    logger.info(f"Target order placed: {target_order_id} at {sl_target_info['target']}")

            # Place Stop-Loss Order  
            if sl_target_info.get('stoploss'):
                sl_result = self.broker.place_order(
                    symbol=symbol,
                    side=exit_side,
                    quantity=quantity,
                    price=sl_target_info['stoploss'],
                    order_type="SL-M"  # Stop-loss market order
                )
                if sl_result.get('success'):
                    stoploss_order_id = sl_result.get('order_id')
                    logger.info(f"Stop-loss order placed: {stoploss_order_id} at {sl_target_info['stoploss']}")

            # Update trade record with SL/Target order IDs
            with get_db_session() as db:
                db.query(Trade).filter(Trade.id == trade_id).update({
                    "target_order_id": target_order_id,
                    "stoploss_order_id": stoploss_order_id,
                    "has_active_target": target_order_id is not None,
                    "has_active_stoploss": stoploss_order_id is not None
                })
                db.commit()

            # Track these orders for monitoring
            with self._lock:
                if target_order_id:
                    self.active_sl_target_orders[target_order_id] = {
                        'trade_id': trade_id, 'type': 'TARGET', 'symbol': symbol
                    }
                if stoploss_order_id:
                    self.active_sl_target_orders[stoploss_order_id] = {
                        'trade_id': trade_id, 'type': 'STOPLOSS', 'symbol': symbol
                    }

        except Exception as e:
            logger.error(f"Error placing SL/Target orders for {trade_id}: {e}")

    def _check_pending_orders(self):
        """Check status of pending orders and update database."""
        
        orders_to_remove = []
        with self._lock:
            pending_order_ids = list(self.pending_orders.keys())
        for order_id in pending_order_ids:
            try:
                logger.info(f"Checking order {order_id}")
                status_result = self.broker.get_order_status(order_id)
                status = status_result.get('status', 'UNKNOWN')
                trade_id = self.pending_orders[order_id]
                logger.info(f"Order status: {status}")
                if status == 'COMPLETE':
                    filled_price = status_result.get('average_price')
                    self._handle_fill(trade_id, filled_price)
                    orders_to_remove.append(order_id)
                    trade_id = self.pending_orders[order_id]
                    if trade_id in getattr(self, 'pending_sl_target', {}):
                        self._place_sl_target_orders(trade_id, self.pending_sl_target[trade_id])
                        del self.pending_sl_target[trade_id]

                elif status in ['CANCELLED', 'REJECTED']:
                    with get_db_session() as db:
                        db.query(Trade).filter(Trade.id == trade_id).update({
                            "status": status,  # Store as string ("CANCELLED"/"REJECTED")
                        })
                        db.commit()
                    orders_to_remove.append(order_id)
                    logger.info(f"Order {status.lower()}: {order_id}")
                
                self._check_sl_target_orders()

            except Exception as e:
                logger.error(f"Error checking order status for {order_id}: {e}")

        with self._lock:
            for order_id in orders_to_remove:
                self.pending_orders.pop(order_id, None)

    def _handle_fill(self, trade_id: str, filled_price: Optional[float]):
        """Handle order fill and update performance metrics."""
        try:
            # Calculate P&L (fill this out as needed)
            pnl = 0.0
            with get_db_session() as db:
                trade = db.query(Trade).filter(Trade.id == trade_id).first()
                if not trade:
                    logger.warning(f"Trade {trade_id} not found in DB during fill handling.")
                    return
                db.query(Trade).filter(Trade.id == trade_id).update({
                    "status": TradeStatus.FILLED.value,
                    "filled_price": filled_price or trade.price,
                    "filled_timestamp": datetime.utcnow(),
                    "pnl": pnl
                })
                db.commit()

                # Optionally update any strategy-state in memory after commit
                strategy = STRATEGY_REGISTRY.get(trade.strategy)
                if strategy:
                    strategy.update_performance(pnl)

                value_to_print = filled_price if filled_price is not None else 0
                logger.info(f"Order filled: {trade.side.value} {trade.quantity} {trade.symbol} @ {value_to_print:.2f} (P&L: {pnl:.2f})")

        except Exception as e:
            logger.error(f"Error handling fill for trade id {trade_id}: {e}")
    
    def _check_sl_target_orders(self):
        """Monitor active SL/Target orders"""
        orders_to_remove = []
        
        with self._lock:
            sl_target_orders = list(self.active_sl_target_orders.keys())
            
        for order_id in sl_target_orders:
            try:
                status_result = self.broker.get_order_status(order_id)
                status = status_result.get('status', 'UNKNOWN')
                order_info = self.active_sl_target_orders[order_id]
                
                if status == 'COMPLETE':
                    # SL or Target hit - update trade
                    self._handle_sl_target_execution(order_id, order_info, status_result)
                    orders_to_remove.append(order_id)
                    
                elif status in ['CANCELLED', 'REJECTED']:
                    # Order cancelled/rejected - clean up
                    self._handle_sl_target_cancellation(order_id, order_info)
                    orders_to_remove.append(order_id)
                    
            except Exception as e:
                logger.error(f"Error checking SL/Target order {order_id}: {e}")

        # Clean up completed orders
        with self._lock:
            for order_id in orders_to_remove:
                self.active_sl_target_orders.pop(order_id, None)

    def _handle_sl_target_execution(self, order_id: str, order_info: dict, status_result: dict):
        """Handle when SL or Target order gets executed"""
        try:
            trade_id = order_info['trade_id']
            order_type = order_info['type']  # 'TARGET' or 'STOPLOSS'
            exit_price = status_result.get('average_price')
            
            with get_db_session() as db:
                trade = db.query(Trade).filter(Trade.id == trade_id).first()
                if trade:
                    # Update trade with exit details
                    trade.exit_price = exit_price
                    trade.exit_timestamp = datetime.utcnow()
                    trade.status = TradeStatus.EXITED.value
                    trade.exit_reason = order_type
                    
                    if order_type == 'TARGET':
                        trade.target_triggered = True
                        # Cancel the corresponding SL order
                        if trade.stoploss_order_id:
                            self._cancel_order_if_exists(trade.stoploss_order_id)
                            trade.has_active_stoploss = False
                            
                    elif order_type == 'STOPLOSS':
                        trade.stoploss_triggered = True
                        # Cancel the corresponding Target order  
                        if trade.target_order_id:
                            self._cancel_order_if_exists(trade.target_order_id)
                            trade.has_active_target = False
                    
                    # Calculate P&L
                    if trade.side.value == "BUY":
                        trade.pnl = (exit_price - trade.effective_price) * trade.quantity
                    else:
                        trade.pnl = (trade.effective_price - exit_price) * trade.quantity
                        
                    db.commit()
                    
                    logger.info(f"{order_type} executed for {trade_id}: Exit price {exit_price}, P&L: {trade.pnl}")

        except Exception as e:
            logger.error(f"Error handling SL/Target execution: {e}")

    def _cancel_order_if_exists(self, order_id: str):
        """Cancel an order if it exists and is still active"""
        try:
            result = self.broker.cancel_order(order_id)
            if result.get('success'):
                logger.info(f"Successfully cancelled order: {order_id}")
                # Remove from active tracking
                with self._lock:
                    self.active_sl_target_orders.pop(order_id, None)
        except Exception as e:
            logger.warning(f"Could not cancel order {order_id}: {e}")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a pending order."""
        try:
            result = self.broker.cancel_order(order_id = order_id)
            logger.info(f"Cancel order is being executed")
            if result.get('success'):
                with get_db_session() as db:
                    trade = db.query(Trade).filter(Trade.order_id == order_id).first()
                    if trade:
                        trade.status = TradeStatus.CANCELLED.value
                        db.commit()
                with self._lock:
                    self.pending_orders.pop(order_id, None)
                logger.info(f"Order cancelled: {order_id}")
            return result
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_pending_orders(self) -> Dict[str, str]:
        with self._lock:
            return self.pending_orders.copy()

    def is_running(self) -> bool:
        return self.running
