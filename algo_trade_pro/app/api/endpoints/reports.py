from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, date, timedelta, time
import os
from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus
from app.services.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))

@router.get("/summary/reports", response_class=HTMLResponse)
async def get_reports(request: Request):
    """Returns a summary report with key metrics, strategy stats, and today's trades as a partial for HTMX."""
    # Calculate "today"
    #logger.info(f"Withing report endpoint")
    today = date.today()
    report_date = today.strftime('%Y-%m-%d')
    generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    year = today.year

    metrics = {
        "total_trades": 0,
        "win_rate": 0.0,
        "total_pnl": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "avg_trade_pnl": 0.0
    }
    strategy_stats = []
    trades = []

    try:
        with get_db_session() as db:
            # 1. Today's trades only (edit filter as needed)
            #logger.info(f"Withing report db")
            #today = date.today()
            report_date = today.strftime('%Y-%m-%d')
            #tomorrow_start = today_start + timedelta(days=1)
            trades_orm = (
                db.query(Trade)
                  .filter(Trade.timestamp >= report_date)
                  .order_by(Trade.timestamp.desc())
                  .all()
            )

            trades = [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side.value if hasattr(t.side, "value") else t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "timestamp": t.timestamp,
                    "filled_timestamp": t.filled_timestamp,
                    "status": t.status.value if hasattr(t.status, "value") else t.status,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "strategy": t.strategy or '',
                }
                for t in trades_orm
            ]

            # 2. Metrics calculations
            #logger.info(f"Withing report metrics")
            metrics["total_trades"] = len(trades)
            if trades:
                wins = [t for t in trades if t["pnl"] is not None and t["pnl"] > 0]
                metrics["win_rate"] = len(wins) / len(trades) if trades else 0
                all_pnl = [t["pnl"] for t in trades if t["pnl"] is not None]
                metrics["total_pnl"] = sum(all_pnl)
                metrics["avg_trade_pnl"] = sum(all_pnl) / len(all_pnl) if all_pnl else 0

                # Max drawdown (simple: lowest cumulative PnL dip)
                cumulative = 0
                max_cum = 0
                min_cum = 0
                for pnl in all_pnl:
                    cumulative += pnl
                    max_cum = max(max_cum, cumulative)
                    min_cum = min(min_cum, cumulative)
                metrics["max_drawdown"] = max_cum - min_cum if min_cum < 0 else 0

                # Simple "sharpe": mean / std, ignore zero stddev
                import numpy as np
                stddev = np.std(all_pnl) if len(all_pnl) > 1 else 1
                metrics["sharpe_ratio"] = (metrics["avg_trade_pnl"] / stddev) if stddev else 0

            # 3. Per-strategy stats for today
            strategy_groups = {}
            for t in trades:
                group = strategy_groups.setdefault(t["strategy"], {
                    "name": t["strategy"],
                    "trades": 0,
                    "win_rate": 0.0,
                    "pnl": 0.0,
                    "sharpe": 0.0,
                    "drawdown": 0.0
                })
                group["trades"] += 1
                group.setdefault("pnls", []).append(t["pnl"] or 0)

            for strat, stats in strategy_groups.items():
                pnls = stats["pnls"]
                stats["pnl"] = sum(pnls)
                stats["win_rate"] = len([p for p in pnls if p > 0]) / len(pnls) if pnls else 0
                # Sharpe/statistics by strategy
                import numpy as np
                stddev = np.std(pnls) if len(pnls) > 1 else 1
                stats["sharpe"] = (np.mean(pnls) / stddev) if stddev else 0
                # Simple drawdown per strategy
                cumulative = 0
                max_cum = 0
                min_cum = 0
                for pnl in pnls:
                    cumulative += pnl
                    max_cum = max(max_cum, cumulative)
                    min_cum = min(min_cum, cumulative)
                stats["drawdown"] = max_cum - min_cum if min_cum < 0 else 0
                # Collapse pnls key
                del stats["pnls"]
                strategy_stats.append(stats)

    except Exception as e:
        print("[/api/v1/reports] Error calculating reports:", e)

    return templates.TemplateResponse("_report.html", {
        "request": request,
        "report_date": report_date,
        "generation_time": generation_time,
        "year": year,
        "metrics": metrics,
        "strategy_stats": strategy_stats,
        "trades": trades
    })
