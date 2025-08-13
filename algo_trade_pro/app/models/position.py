from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from app.models.database import Base


class Position(Base):
    """
    ORM model for open positions currently held by the algo trading system.
    """
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)               # NSE/BSE symbol
    quantity = Column(Integer, nullable=False, default=0)     # +ve for long, -ve for short
    avg_price = Column(Float, nullable=False, default=0.0)    # Weighted average entry price
    current_price = Column(Float, nullable=True)              # Latest market price
    pnl = Column(Float, nullable=True)                        # Unrealized P&L
    last_updated = Column(DateTime, default=datetime.utcnow)  # Last updated timestamp

    def __repr__(self):
        return (f"<Position[{self.symbol}] Qty={self.quantity} "
                f"AvgPrice={self.avg_price} PnL={self.pnl:.2f}>")
