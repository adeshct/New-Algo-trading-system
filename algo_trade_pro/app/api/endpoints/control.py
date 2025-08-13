"""
app/api/endpoints/control.py

Control API endpoints for starting/stopping/restarting the algo engine and threads.
Integrates with AlgoController and platform status routines.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict

from app.core.controller import AlgoController
from app.services.logger import get_logger
#from app.main import controller as global_controller


router = APIRouter()
logger = get_logger(__name__)

# Note: Make sure your main.py or FastAPI app creates a single, global controller instance.
try:
    from app.main import controller as global_controller  # Import the global controller from your main app file
    
except ImportError:
    global_controller = None

def get_controller() -> AlgoController:
    if global_controller is None:
        logger.error("AlgoController is not initialized.")
        raise HTTPException(status_code=500, detail="AlgoController not running.")
    return global_controller

@router.post("/start", response_model=dict)
async def start_engine(request: Request):
    """Start all trading threads"""
    controller = request.app.state.controller
    await controller.start_all()
    logger.info("Algo engine started via /control/start endpoint.")
    return {"status": "started"}

@router.post("/stop", response_model=dict)
async def stop_engine(request: Request):
    """Stop all trading threads"""
    controller = request.app.state.controller
    await controller.stop_all()
    logger.info("Algo engine stopped via /control/stop endpoint.")
    return {"status": "stopped"}

@router.post("/restart/{component}", response_model=dict)
async def restart_component(component: str):
    """
    Restart a specific subcomponent: data_collector, strategy_engine, trade_executor, risk_manager, scheduler
    """
    controller = get_controller()
    await controller.restart_component(component)
    logger.info(f"Component '{component}' restarted via /control/restart/{component}.")
    return {"status": "restarted", "component": component}

@router.get("/status", response_model=Dict)
async def engine_status():
    """Get the status of all trading components/threads"""
    controller = get_controller()
    status = await controller.get_status()
    return status
