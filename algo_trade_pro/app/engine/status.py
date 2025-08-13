#from app.main import controller
from fastapi import Request
from app.services.logger import get_logger
logger = get_logger(__name__)




def get_engine_status(request: Request):
    controller = request.app.state.controller
    if not controller:
        return {
            "status": "Idle",
            "strategies_active": 0,
            "data_collector": False,
            "strategy_engine": False,
            "trade_executor": False,
            "risk_manager": False,
        }
    
    enabled_count = sum(1 for s in controller.strategy_engine.active_strategies if s.is_enabled())

    return {
        "status": "Running" if controller.is_running else "Idle",
        "strategies_active": sum(1 for s in controller.strategy_engine.active_strategies if s.is_enabled()),
        "data_collector": controller.threads.get("data_collector", None).is_alive()
            if controller.threads.get("data_collector") else False,
        "strategy_engine": controller.threads.get("strategy_engine", None).is_alive()
            if controller.threads.get("strategy_engine") else False,
        "trade_executor": controller.threads.get("trade_executor", None).is_alive()
            if controller.threads.get("trade_executor") else False,
        "risk_manager": controller.threads.get("risk_manager", None).is_alive()
            if controller.threads.get("risk_manager") else False,
    }