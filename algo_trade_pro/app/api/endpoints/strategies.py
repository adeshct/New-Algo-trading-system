from fastapi import APIRouter, HTTPException, Body, Form
from typing import List
from app.strategies.registry import STRATEGY_REGISTRY
from app.core.controller import AlgoController
from app.models.schema import StrategyControlRequest
from pydantic import BaseModel
from app.services.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

class StrategyControlRequest(BaseModel):
    strategy_name: str
    enable: bool

# Typically, you would inject this via dependency, but for direct startup:
try:
    from app.main import controller  # Main controller singleton, started at FastAPI app startup
except ImportError:
    controller = None  # For IDE/static type checkers

@router.get("/", response_model=List[str])
async def list_strategies():
    """List all available strategies with their status."""
    strategies = []
    
    for name, strategy in STRATEGY_REGISTRY.items():
        metrics = strategy.get_performance_metrics()
        strategies.append({
            "name": name,
            "enabled": strategy.is_enabled(),
            "symbols": strategy.symbols,
            "metrics": metrics
        })
    
    return {"strategies": strategies}

@router.post("/control")
async def control_strategy(
    strategy_name: str = Form(...),
    enable: bool = Form(...)
):
    strategy = STRATEGY_REGISTRY.get(strategy_name)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if enable:
        strategy.enable()
        logger.info(f"Strategy {strategy_name} enabled via API")
    else:
        strategy.disable()
        logger.info(f"Strategy {strategy_name} disabled via API")

    return {
        "success": True,
        "strategy": strategy_name,
        "enabled": strategy.is_enabled(),
        "message": f"Strategy {'enabled' if enable else 'disabled'}"
    }

@router.get("/status/{strategy_name}", response_model=dict)
def strategy_status(strategy_name: str):
    """Fetch basic performance metrics for a named strategy."""
    if not controller or not hasattr(controller, "strategy_engine"):
        raise HTTPException(status_code=500, detail="Strategy engine not initialized")
    metrics = controller.strategy_engine.get_strategy_performance(strategy_name)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    return {"strategy": strategy_name, "metrics": metrics}

@router.get("/pnl/{strategy_name}")
def get_strategy_pnl(strategy_name: str):
    return get_realtime_strategy_pnl(strategy_name)

@router.get("/{strategy_name}")
async def get_strategy(strategy_name: str):
    """Get detailed information about a specific strategy."""
    strategy = STRATEGY_REGISTRY.get(strategy_name)
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {
        "name": strategy.name,
        "enabled": strategy.is_enabled(),
        "symbols": strategy.symbols,
        "min_data_points": strategy.min_data_points,
        "metrics": strategy.get_performance_metrics()
    }