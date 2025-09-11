import asyncio
import threading
import time
from typing import Dict, Any
from app.core.data_collector import DataCollector
from app.core.strategy_engine import StrategyEngine
from app.core.trade_executor import TradeExecutor
from app.core.risk_manager import RiskManager
from app.services.logger import get_logger
from app.config.settings import get_settings
from app.brokers.zerodha import ZerodhaBroker
from app.brokers.custom_broker import CustomBroker
from app.core.sl_target_monitor import SLTargetMonitor

logger = get_logger(__name__)
settings = get_settings()


class AlgoController:
    """Main controller that manages all trading system components."""

    def __init__(self):
        self.is_running = False
        self.components = {}
        self.threads = {}
        self.broker = self._initialize_broker()
        
        # Initialize components
        self.data_collector = DataCollector(self.broker)
        self.strategy_engine = StrategyEngine() 
        self.trade_executor = TradeExecutor(self.broker)
        self.risk_manager = RiskManager()
        
        self.sl_target_monitor = SLTargetMonitor(self.broker, self.data_collector)
        self.components['sl_target_monitor'] = self.sl_target_monitor
        
        self.components = {
            'data_collector': self.data_collector,
            'strategy_engine': self.strategy_engine,
            'trade_executor': self.trade_executor,
            'risk_manager': self.risk_manager
        }
        
        logger.info("AlgoController initialized with all components")

    def _initialize_broker(self):
        """Initialize the appropriate broker based on configuration."""
        broker_type = settings.BROKER.lower()
        
        if broker_type == "zerodha" and settings.ZERODHA_ACCESS_TOKEN:
            if broker_type == "zerodha" and settings.ZERODHA_ACCESS_TOKEN:
                try:
                    return ZerodhaBroker()
                except Exception as e:
                    logger.error(f"Failed to initialize Zerodha broker: {e}")
                    return CustomBroker()
            else:
                logger.warning("No broker token found. Using CustomBroker temporarily.")
                return CustomBroker()

    def inject_broker(self, broker_instance):
        """Dynamically set/replace the broker system-wide"""
        self.broker = broker_instance
        self.trade_executor.broker = broker_instance
        self.data_collector.broker = broker_instance
        logger.info(f"Injected new broker: {type(broker_instance).__name__}")

    async def start_all(self):
        """Start all trading system components."""
        if self.is_running:
            logger.warning("AlgoController is already running")
            return

        logger.info("Starting all trading system components...")
        self.is_running = True
        
        # Start components in separate threads
        self._start_component_threads()
        
        logger.info("All components started successfully")

    def _start_component_threads(self):
        """Start each component in its own thread."""
        thread_configs = [
            ('data_collector', self.data_collector.run, "Data collection thread started"),
            ('strategy_engine', self.strategy_engine.run, "Strategy engine thread started"),
            ('trade_executor', self.trade_executor.run, "Trade executor thread started"),
            ('risk_manager', self.risk_manager.run, "Risk manager thread started")
            ('sl_target_monitor', self.sl_target_monitor.run, "SL/Target monitor thread started")
        ]
        
        for name, target, message in thread_configs:
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads[name] = thread
            logger.info(message)

    async def stop_all(self):
        """Stop all trading system components."""
        if not self.is_running:
            logger.warning("AlgoController is not running")
            return

        logger.info("Stopping all trading system components...")
        self.is_running = False

        # Stop all components
        for name, component in self.components.items():
            try:
                component.stop()
                logger.info(f"Stopped {name}")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        # Wait for threads to finish (with timeout)
        for name, thread in self.threads.items():
            try:
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(f"Thread {name} did not stop gracefully")
                else:
                    logger.info(f"Thread {name} stopped")
            except Exception as e:
                logger.error(f"Error stopping thread {name}: {e}")
        
        if self.strategy_engine:
            for strategy in self.strategy_engine.active_strategies:
                strategy.disable()
                logger.info(f"Disabled strategy: {strategy.name}")

        self.threads.clear()
        logger.info("All threads and components stopped")

    async def restart_component(self, component_name: str):
        """Restart a specific component."""
        if component_name not in self.components:
            raise ValueError(f"Unknown component: {component_name}")

        logger.info(f"Restarting component: {component_name}")
        
        # Stop the component
        component = self.components[component_name]
        component.stop()
        
        # Wait for thread to stop
        if component_name in self.threads:
            self.threads[component_name].join(timeout=5)
        
        # Restart the component
        if component_name == 'data_collector':
            target_func = self.data_collector.run
        elif component_name == 'strategy_engine':
            target_func = self.strategy_engine.run
        elif component_name == 'trade_executor':
            target_func = self.trade_executor.run
        elif component_name == 'risk_manager':
            target_func = self.risk_manager.run
        else:
            raise ValueError(f"Unknown component: {component_name}")
        
        thread = threading.Thread(target=target_func, daemon=True, name=f"AlgoTrade-{component_name}")
        thread.start()
        self.threads[component_name] = thread
        
        logger.info(f"Component {component_name} restarted successfully")

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all components."""
        status = {
            "running": self.is_running,
            "broker_type": type(self.broker).__name__,
            "components": {},
            "threads": {}
        }
        
        # Component status
        for name, component in self.components.items():
            status["components"][name] = {
                "running": getattr(component, 'running', False),
                "status": "active" if getattr(component, 'running', False) else "stopped"
            }
        
        # Thread status
        for name, thread in self.threads.items():
            status["threads"][name] = {
                "alive": thread.is_alive(),
                "name": thread.name
            }
        
        # Add performance metrics
        if hasattr(self.strategy_engine, 'get_active_strategies'):
            active_strategies = self.strategy_engine.get_active_strategies()
            status["active_strategies"] = len(active_strategies)
        
        return status

    def get_broker(self):
        """Get the current broker instance."""
        return self.broker
    
    def is_running(self) -> bool:
        """Check if controller is running."""
        return self.is_running