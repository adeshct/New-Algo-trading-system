from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.engine.status import get_engine_status  # Your own logic or dummy
import os
from app.core.controller import AlgoController
from app.strategies.registry import STRATEGY_REGISTRY
from app.services.logger import get_logger
#from app.core.performance import get_pnl_metrics

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))
logger = get_logger(__name__)
# def get_engine_status():
#     return {
#         "status": "Running" if controller and controller.is_running else "Idle",
#         "strategy_thread": controller.strategy_thread.is_alive() if controller else False,
#         # check and report other threads similarly
#     }


def get_pnl_metrics() -> dict:
    """Get current P&L metrics across all strategies."""
    total_pnl = 0.0
    today_pnl = 0.0
    total_trades = 0
    total_wins = 0
    max_drawdown = 0.0
    
    for strategy in STRATEGY_REGISTRY.values():
        metrics = strategy.get_performance_metrics()
        total_pnl += metrics["total_pnl"]
        total_trades += metrics["trades_executed"]
        total_wins += metrics["win_count"]
        max_drawdown = max(max_drawdown, metrics["max_drawdown"])
    
    win_rate = total_wins / total_trades if total_trades > 0 else 0.0
    
    return {
        "today_pnl": today_pnl,  # Can be enhanced to track daily P&L separately
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown
    }

@router.get("/system/status", response_class=HTMLResponse)
async def system_status(request: Request):
    """Get system status as HTML partial for HTMX."""
    status = get_engine_status(request)
    logger.info(f"Status of the request: {status}")
    return templates.TemplateResponse("_system_status.html", {
        "request": request,
        "status": status
    })


@router.get("/system/pnl", response_class=HTMLResponse)
async def system_pnl(request: Request):
    """Get P&L metrics as HTML partial for HTMX."""
    metrics = get_pnl_metrics()
    return templates.TemplateResponse("_system_pnl.html", {
        "request": request,
        "metrics": metrics
    })


@router.get("/market/indices", response_class=HTMLResponse)
async def market_indices(request: Request):
    """Get market indices as HTML partial for HTMX."""
    # Mock data - in production, fetch from market data provider
    controller = getattr(request.app.state, "controller", None)
    broker = getattr(controller, "broker", None)

    index_symbols = ["NIFTY 50", "SENSEX", "NIFTY BANK"]
    indices = {}

    if broker is None:
        # Return empty-ish values when not connected
        for symbol in index_symbols:
            indices[symbol] = {
                "value": "--",
                "change": "--",
                "change_pct": "--"
            }
    else:
        for symbol in index_symbols:
            try:
                quote = broker.get_quote(symbol)
                if quote:
                    change = quote["ltp"] - quote["open"]
                    change_pct = (change / quote["open"]) * 100 if quote["open"] != 0 else 0.0
                    indices[symbol] = {
                        "value": round(quote["ltp"], 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2)
                    }
                else:
                    indices[symbol] = {
                        "value": "N/A", "change": "N/A", "change_pct": "N/A"
                    }
            except Exception as e:
                indices[symbol] = {
                    "value": "ERR", "change": "-", "change_pct": "-"
                }

    return templates.TemplateResponse("_market_indices.html", {
        "request": request,
        "indices": indices
    })

@router.get("/api/market_data/live")
async def get_live_market_data():
    from app.queue.signal_queue import latest_tick
    return {"success": True, "data": latest_tick}

@router.get("/api/signals/live")
async def get_live_signals():
    from app.queue.signal_queue import latest_signals
    return {"success": True, "signals": latest_signals}
