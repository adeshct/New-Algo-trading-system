from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =====================
# Trade Schemas
# =====================

class TradeBase(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    price: float
    strategy: Optional[str] = None


class TradeCreate(TradeBase):
    pass


class TradeResponse(TradeBase):
    id: str
    status: str
    timestamp: datetime
    filled_price: Optional[float] = None
    filled_timestamp: Optional[datetime] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        orm_mode = True


# =====================
# Position Schema
# =====================

class PositionResponse(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    current_price: Optional[float]
    pnl: Optional[float]
    last_updated: Optional[datetime]

    class Config:
        orm_mode = True


# =====================
# System Log Schema
# =====================

class LogEntry(BaseModel):
    id: int
    level: str
    event_type: str
    message: str
    timestamp: datetime
    thread: Optional[str]
    strategy: Optional[str]
    symbol: Optional[str]
    context: Optional[str]

    class Config:
        orm_mode = True


# =====================
# API Request Schemas
# =====================

class SignalInput(BaseModel):
    symbol: str
    action: str  # "BUY" or "SELL"
    price: float
    quantity: int = Field(..., gt=0)
    strategy: Optional[str] = "Manual"
    signal_type: Optional[str] = "Manual"
    timestamp: Optional[datetime] = None


class StrategyControlRequest(BaseModel):
    strategy_name: str
    enable: bool


class ForceCloseRequest(BaseModel):
    symbol: str
    reason: Optional[str] = "Manual force close"
