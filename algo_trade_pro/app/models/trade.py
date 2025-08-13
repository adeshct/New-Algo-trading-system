import uuid
import enum
from enum import Enum
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Enum as PgEnum, DateTime, Text

from app.models.database import Base


class TradeStatus(str, Enum):
    """States a trade can go through in its lifecycle"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXITED = "EXITED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

class TradeSide(enum.Enum):
    """Trade side enumeration."""
    BUY = "BUY"
    SELL = "SELL"

class Trade(Base):
    """
    ORM model representing a trade executed by a strategy or manually.
    """
    __tablename__ = "trades"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20), nullable=False)
    side = Column(PgEnum(TradeSide, native_enum=False), nullable=False)  # BUY or SELL
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)     # Suggested price by strategy
    filled_price = Column(Float, nullable=True)      # Actual price where order executed
    strategy = Column(String(50), nullable=True)     # Strategy that generated this trade
    status = Column(PgEnum(TradeStatus), default=TradeStatus.PENDING)

    timestamp = Column(DateTime, default=datetime.utcnow)       # When signal generated
    filled_timestamp = Column(DateTime, nullable=True)          # When order got filled

    order_id = Column(String(50), nullable=True)                # Broker order reference
    error_message = Column(Text, nullable=True)                 # If rejected/failed

    stop_loss = Column(Float, nullable=True)                    # Suggested SL by strategy
    target = Column(Float, nullable=True)                       # Suggested target by strategy

    pnl = Column(Float, nullable=True, default=0.0)
    #commission = Column(Float, nullable=True, default=0.0)             # Calculated P&L
    exit_price = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime, nullable=True)            # Optional exit time

    def __repr__(self):
        return (f"<Trade[{self.id}] {self.side} {self.quantity} {self.symbol} "
                f"@{self.price} Status={self.status}>")
    
    @property
    def is_buy(self) -> bool:
        """Check if this is a buy trade."""
        return self.side == TradeSide.BUY
    
    @property
    def is_sell(self) -> bool:
        """Check if this is a sell trade."""
        return self.side == TradeSide.SELL
    
    @property
    def is_filled(self) -> bool:
        """Check if trade is filled."""
        return self.status == TradeStatus.FILLED
    
    @property
    def effective_price(self) -> float:
        """Get the effective price (filled price if available, otherwise order price)."""
        return self.filled_price if self.filled_price is not None else self.price
    
    def calculate_pnl(self, current_price: Optional[float] = None) -> Optional[float]:
        """Calculate P&L for this trade."""
        if not self.is_filled:
            return None
        
        if self.pnl is not None:
            return self.pnl
        
        if current_price is None:
            current_price = self.filled_price or self.price
        
        if self.is_buy:
            return (current_price - self.effective_price) * self.quantity
        else:  # SELL
            return (self.effective_price - current_price) * self.quantity