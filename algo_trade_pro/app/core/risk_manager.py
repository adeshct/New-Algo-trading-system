
import time
import threading
from typing import Dict, List, Any
from datetime import datetime, timedelta
from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus
from app.services.logger import get_logger
from app.config.settings import get_settings
from app.strategies.registry import STRATEGY_REGISTRY

logger = get_logger(__name__)
settings = get_settings()


class RiskManager:
    """Risk management and monitoring system."""

    def __init__(self):
        self.running = False
        self.alerts = []
        self.position_limits = {}
        self.daily_loss_limit = settings.MAX_DAILY_LOSS
        self.max_position_size = settings.MAX_POSITION_SIZE
        self._lock = threading.Lock()

    def run(self):
        """Main risk monitoring loop."""
        self.running = True
        logger.info("Risk manager started")
        
        while self.running:
            try:
                self._check_risk_limits()
                self._monitor_positions()
                self._check_daily_limits()
                time.sleep(settings.RISK_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in risk management: {e}")
                time.sleep(10)
        
        logger.info("Risk manager stopped")

    def stop(self):
        """Stop risk monitoring."""
        self.running = False
        logger.info("Risk manager stopping...")

    def _check_risk_limits(self):
        """Check various risk limits and constraints."""
        try:
            # Check strategy-level limits
            for strategy_name, strategy in STRATEGY_REGISTRY.items():
                if not strategy.is_enabled():
                    continue
                
                metrics = strategy.get_performance_metrics()
                
                # Check maximum drawdown
                if metrics['max_drawdown'] > (self.max_position_size * 0.1):  # 10% of max position
                    self._create_alert(
                        "HIGH_DRAWDOWN",
                        f"Strategy {strategy_name} has high drawdown: {metrics['max_drawdown']:.2f}",
                        "WARNING"
                    )
                
                # Check win rate degradation
                if metrics['trades_executed'] > 10 and metrics['win_rate'] < 0.3:  # Less than 30% win rate
                    self._create_alert(
                        "LOW_WIN_RATE",
                        f"Strategy {strategy_name} has low win rate: {metrics['win_rate']*100:.1f}%",
                        "WARNING"
                    )
        
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")

    def _monitor_positions(self):
        """Monitor current positions and exposure."""
        try:
            with get_db_session() as db:
                # Get active positions
                active_trades = db.query(Trade).filter(
                    Trade.status.in_([TradeStatus.FILLED, TradeStatus.ACTIVE])
                ).all()
                
                # Calculate position sizes by symbol
                positions = {}
                for trade in active_trades:
                    symbol = trade.symbol
                    if symbol not in positions:
                        positions[symbol] = {'quantity': 0, 'value': 0.0}
                    
                    multiplier = 1 if trade.side.value == "BUY" else -1
                    positions[symbol]['quantity'] += (trade.quantity * multiplier)
                    positions[symbol]['value'] += (trade.quantity * trade.effective_price * multiplier)
                
                # Check position limits
                for symbol, position in positions.items():
                    position_value = abs(position['value'])
                    
                    if position_value > self.max_position_size:
                        self._create_alert(
                            "POSITION_LIMIT_BREACH",
                            f"Position in {symbol} exceeds limit: {position_value}",
                            "CRITICAL"
                        )
        
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")

    def _check_daily_limits(self):
        """Check daily P&L and loss limits."""
        try:
            today = datetime.utcnow().date()
            
            with get_db_session() as db:
                # Get today's trades
                today_trades = db.query(Trade).filter(
                    Trade.filled_timestamp >= datetime.combine(today, datetime.min.time()),
                    Trade.status == TradeStatus.FILLED
                ).all()
                
                # Calculate daily P&L
                daily_pnl = sum(trade.pnl or 0 for trade in today_trades)
                
                # Check daily loss limit
                if daily_pnl < -self.daily_loss_limit:
                    self._create_alert(
                        "DAILY_LOSS_LIMIT",
                        f"Daily loss limit breached: {daily_pnl:.2f}",
                        "CRITICAL"
                    )
                    
                    # Disable all strategies
                    self._emergency_stop("Daily loss limit exceeded")
        
        except Exception as e:
            logger.error(f"Error checking daily limits: {e}")

    def _create_alert(self, alert_type: str, message: str, severity: str):
        """Create and log a risk alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow()
        }
        
        with self._lock:
            self.alerts.append(alert)
            
            # Keep only last 100 alerts
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]
        
        logger.warning(f"RISK ALERT [{severity}]: {message}")

    def _emergency_stop(self, reason: str):
        """Emergency stop all trading activities."""
        logger.critical(f"EMERGENCY STOP: {reason}")
        
        # Disable all strategies
        for strategy in STRATEGY_REGISTRY.values():
            if strategy.is_enabled():
                strategy.disable()
                logger.warning(f"Disabled strategy {strategy.name} due to emergency stop")
        
        self._create_alert("EMERGENCY_STOP", f"Emergency stop triggered: {reason}", "CRITICAL")

    def get_current_exposure(self) -> Dict[str, Any]:
        """Get current market exposure and risk metrics."""
        try:
            with get_db_session() as db:
                active_trades = db.query(Trade).filter(
                    Trade.status.in_([TradeStatus.FILLED, TradeStatus.ACTIVE])
                ).all()
                
                total_exposure = 0.0
                positions_count = 0
                
                positions = {}
                for trade in active_trades:
                    symbol = trade.symbol
                    if symbol not in positions:
                        positions[symbol] = 0.0
                        positions_count += 1
                    
                    multiplier = 1 if trade.side.value == "BUY" else -1
                    position_value = trade.quantity * trade.effective_price * multiplier
                    positions[symbol] += position_value
                    total_exposure += abs(position_value)
                
                return {
                    "total_exposure": total_exposure,
                    "positions_count": positions_count,
                    "max_exposure_limit": self.max_position_size,
                    "exposure_ratio": total_exposure / self.max_position_size,
                    "positions": positions
                }
        
        except Exception as e:
            logger.error(f"Error calculating exposure: {e}")
            return {"error": str(e)}

    def get_daily_pnl(self) -> float:
        """Get today's total P&L."""
        try:
            today = datetime.utcnow().date()
            
            with get_db_session() as db:
                today_trades = db.query(Trade).filter(
                    Trade.filled_timestamp >= datetime.combine(today, datetime.min.time()),
                    Trade.status == TradeStatus.FILLED
                ).all()
                
                return sum(trade.pnl or 0 for trade in today_trades)
        
        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            return 0.0

    def get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent risk alerts."""
        with self._lock:
            return self.alerts[-limit:] if self.alerts else []

    def clear_alerts(self):
        """Clear all alerts."""
        with self._lock:
            self.alerts.clear()
        logger.info("Risk alerts cleared")

    def is_running(self) -> bool:
        """Check if risk manager is running."""
        return self.running