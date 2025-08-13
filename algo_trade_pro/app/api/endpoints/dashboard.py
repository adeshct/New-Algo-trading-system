from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.core.controller import AlgoController
from app.strategies.registry import STRATEGY_REGISTRY
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))

def get_strategy_metrics():
    """Get performance metrics for all strategies."""
    return [
        {
            "name": s.name,
            "enabled": s.is_enabled(),
            "metrics": s.get_performance_metrics()
        }
        for s in STRATEGY_REGISTRY.values()
    ]

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/dashboard/strategy-table")
async def strategy_table(request: Request):
    # For htmx partial
    strategies = get_strategy_metrics()
    return templates.TemplateResponse("_strategy_table.html", {"request": request, "strategies": strategies})

@router.get("/dashboard/strategy-cards", response_class=HTMLResponse)
async def get_strategy_cards(request: Request):
    """Get strategy cards as HTML partial for HTMX."""
    strategies = get_strategy_metrics()
    return templates.TemplateResponse("_strategy_cards.html", {
        "request": request,
        "strategies": strategies
    })

@router.get("/dashboard/pnl-chart", response_class=HTMLResponse)
async def pnl_chart(request: Request, strategy: str = Query(...)):
    # Dummy example: Use STRATEGY_REGISTRY[strategy].get_performance_metrics()['cum_pnl_series']
    strat = STRATEGY_REGISTRY[strategy]
    trade_pnls = strat._performance.get("trade_pnls", [])
    cum_pnl = []
    total = 0
    for pnl in trade_pnls:
        total += pnl
        cum_pnl.append(total)
    pnl_data = {
        "x": list(range(1, len(cum_pnl) + 1)),
        "y": cum_pnl,
    }
    return templates.TemplateResponse("_pnl_chart.html", {"request": request, "pnl_data": pnl_data, "strategy_name": strategy})
