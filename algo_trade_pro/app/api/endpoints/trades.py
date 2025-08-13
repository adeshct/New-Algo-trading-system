from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime

from app.services.logger import get_logger
from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus
from app.models.schema import TradeResponse, TradeCreate

router = APIRouter()
logger = get_logger(__name__)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))

def get_session():
    with get_db_session() as session:
        yield session

# Get all trades or filter by symbol/status/strategy
@router.get("/", response_model=List[TradeResponse])
def list_trades(
    symbol: Optional[str] = Query(None, description="Stock symbol"),
    status: Optional[TradeStatus] = Query(None, description="Trade status"),
    strategy: Optional[str] = Query(None, description="Strategy name"),
    limit: int = Query(100, description="How many trades to return"),
    db: Session = Depends(get_session),
):
    query = db.query(Trade)
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    if status:
        query = query.filter(Trade.status == status)
    if strategy:
        query = query.filter(Trade.strategy == strategy)
    trades = query.order_by(Trade.timestamp.desc()).limit(limit).all()
    return trades

# Get a trade by ID
@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: str, db: Session = Depends(get_session)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found at get_trade")
    return trade

# Create a new trade (manual inject, not from signal/strategy)
@router.post("/", response_model=TradeResponse)
def create_trade(trade: TradeCreate, db: Session = Depends(get_session)):
    db_trade = Trade(
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        strategy=trade.strategy,
        status=TradeStatus.PENDING
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

# Delete (cancel) a trade (before execution)
@router.delete("/{trade_id}", response_model=TradeResponse)
def delete_trade(trade_id: str, db: Session = Depends(get_session)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found at delete trade")
    if trade.status != TradeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Can only cancel pending trades")
    trade.status = TradeStatus.CANCELLED
    db.commit()
    db.refresh(trade)
    return trade

@router.get("/trades/live", response_class=HTMLResponse)
async def live_trades(request: Request):
    trades_data = []

    # ✅ Step 2: Add broker-side pending orders
    try:
        controller = getattr(request.app.state, "controller", None)
        broker = getattr(controller, "broker", None)

        if broker is not None and hasattr(broker, "get_pending_orders"):
            pending_orders = broker.get_pending_orders()
            for o in pending_orders:
                trades_data.append({
                    "id": f"broker-{o.get('order_id')}",
                    "source": "broker",
                    "order_id": o.get("order_id"),
                    "symbol": o.get("tradingsymbol"),
                    "side": o.get("transaction_type"),
                    "quantity": o.get("quantity"),
                    "price": o.get("price") or 0,
                    "timestamp": o.get("order_timestamp") or datetime.utcnow(),
                    "status": o.get("status"),
                    "pnl": "—",  # P&L doesn't exist from broker order info
                })
        else:
            print("[trades/live]: Broker not connected or missing method")
    except Exception as e:
        print(f"[trades/live error - Broker]: {e}")

    # ✅ Step 3: Return trimmed + enriched trade list
    return templates.TemplateResponse("_live_trades.html", {
        "request": request,
        "trades": trades_data
    })

@router.get("/trades/history", response_class=HTMLResponse)
async def trade_history(request: Request):
    """Get full trade history as HTML partial for HTMX."""
    try:
        with get_db_session() as db:
            trades = (
                db.query(Trade)
                .order_by(Trade.timestamp.desc())
                .limit(100)  # or remove limit for all
                .all()
            )
            trades_data = [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side.value if hasattr(t.side, "value") else t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "timestamp": t.timestamp,
                    "status": t.status.value if hasattr(t.status, "value") else t.status,
                    "pnl": t.pnl,
                }
                for t in trades
            ]
    except Exception as e:
        print(f"[trades/history error]: {e}")
        trades_data = []
    return templates.TemplateResponse("_trade_history.html", {
        "request": request,
        "trades": trades_data
    })

@router.get("/positions/active", response_class=HTMLResponse)
async def active_positions(request: Request):
    """
    Get active positions (live, from broker) as HTML partial for HTMX.
    """
    positions = []
    # This assumes your broker class or SDK returns a list of position dicts
    try:
        broker_positions = request.app.state.controller.broker.get_positions()  # Synchronous
        # OR: broker_positions = await controller.broker.get_positions() if async

        for pos in broker_positions:
            positions.append({
                "symbol": pos["symbol"],
                "side": pos["side"],
                "quantity": float(pos["quantity"]),
                "avg_price": float(pos["avg_price"]),
                "current_price": float(pos["current_price"]),
                "pnl": float(pos.get("pnl", 0.0) or 0.0)
            })
    except Exception as e:
        # You might want to log and/or show a special error row in production
        print(f"[ERROR] Could not fetch broker positions: {e}")

    return templates.TemplateResponse("_active_positions.html", {
        "request": request,
        "positions": positions
    })

@router.get("/broker/holdings", response_class=HTMLResponse)
async def broker_holdings(request: Request):
    broker = getattr(request.app.state.controller, "broker", None)
    holdings = []
    error_msg = None

    if broker:
        try:
            response = broker.get_holdings()
            if response.get("success"):
                holdings = response["holdings"]
            else:
                error_msg = response.get("error", "Unable to fetch holdings.")
        except Exception as e:
            error_msg = str(e)
    else:
        error_msg = "Broker not connected."

    return templates.TemplateResponse("_holdings.html", {
        "request": request,
        "holdings": holdings,
        "error": error_msg
    })

@router.post("/trades/cancel")
async def cancel_trade(
    request: Request,
    order_id: str = Form(...),  # Broker or DB order ID
    broker: str = Form("local"),  # Optional flag (local or zerodha)
    status: str = Form(...) #VARIETY OF THE ORDER
):
    controller = request.app.state.controller

    try:
        logger.info(f"Cancel requested for order: {order_id} (broker={broker})")

        # If cancel from broker
        if broker.lower() == "zerodha":
            result = controller.broker.cancel_order(order_id = order_id)
            if result.get("success"):
                # Try updating DB order if it exists
                with get_db_session() as db:
                    trade = db.query(Trade).filter(Trade.order_id == order_id).first()
                    if trade:
                        trade.status = TradeStatus.CANCELLED.value
                        db.commit()
                return {"success": True, "message": "Order cancelled at broker and DB updated"}

        # Else use local trade executor (DB originated)
        result = controller.trade_executor.cancel_order(order_id)
        if result.get("success"):
            with get_db_session() as db:
                trade = db.query(Trade).filter(Trade.order_id == order_id).first()
                if trade:
                    trade.status = TradeStatus.CANCELLED.value
                    db.commit()
            return {"success": True, "message": "Order cancelled in DB"}

        return {"success": False, "error": result.get("error", "Cancel failed")}

    except Exception as e:
        logger.error(f"Trade cancel error: {e}")
        return {"success": False, "error": str(e)}

@router.post("/trades/exit")
async def exit_trade(
    request: Request,
    trade_id: Optional[str] = Form(None),
    order_id: Optional[str] = Form(None),
    broker: str = Form("local")
):
    controller = request.app.state.controller

    try:
        if broker.lower() == "zerodha" and order_id:
            logger.info(f"Broker exit submitted for order_id: {order_id}")

            # Fetch order details if needed, or just re-place counter order
            # You can expand this with symbol qty mapping if needed
            exit_side = "SELL" if str(trade.side).upper() == "BUY" else "BUY"
            result = controller.broker.place_order(
                symbol=trade.symbol,
                side=exit_side,
                quantity=trade.quantity,
                price=0,  # MARKET price, so price is ignored
                order_type="MARKET"
            )

            if result.get("success"):
                with get_db_session() as db:
                    trade = db.query(Trade).filter(Trade.order_id == order_id).first()
                    if trade:
                        trade.status = TradeStatus.EXITED.value
                        db.commit()

                return {"success": True, "message": "Order exited at broker"}

            return {"success": False, "error": result.get("error", "Exit failed at broker")}

        # Handle local DB trade exit (your existing logic)
        if not trade_id:
            return {"success": False, "error": "Trade ID required for local exit"}

        with get_db_session() as db:
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            if not trade or trade.status not in [TradeStatus.FILLED.value, TradeStatus.ACTIVE.value]:
                return {"success": False, "error": "Trade not eligible to exit"}

            exit_side = "SELL" if trade.side == "BUY" else "BUY"
            result = controller.broker.place_order(
                symbol=trade.symbol,
                side=exit_side,
                quantity=trade.quantity,
                price=None,
                order_type="MARKET"
            )

            if result.get("success"):
                trade.status = TradeStatus.EXITED.value
                db.commit()

            return {"success": result.get("success", False)}

    except Exception as e:
        logger.error(f"Trade exit error: {e}")
        return {"success": False, "error": str(e)}