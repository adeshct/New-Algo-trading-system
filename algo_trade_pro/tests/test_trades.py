import pytest
from datetime import datetime

from app.models.trade import Trade, TradeStatus
from app.models.database import get_db_session, Base, engine

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_trade_creation():
    now = datetime.utcnow()
    trade = Trade(
        id="T-123",
        symbol="INFY",
        side="BUY",
        quantity=100,
        price=1500.0,
        filled_price=1502.0,
        strategy="TestStrategy",
        status=TradeStatus.FILLED,
        timestamp=now,
        filled_timestamp=now,
        pnl=200.0
    )

    with get_db_session() as db:
        db.add(trade)
        db.commit()

        result = db.query(Trade).filter_by(symbol="INFY").first()
        assert result is not None
        assert result.strategy == "TestStrategy"
        assert result.filled_price == 1502.0
        assert round(result.pnl, 2) == 200.0

def test_trade_update_status():
    now = datetime.utcnow()
    with get_db_session() as db:
        t = Trade(id="UPD-001", symbol="TCS", side="SELL", quantity=10, price=3200, status=TradeStatus.PENDING, strategy="MA_Test", timestamp=now)
        db.add(t)
        db.commit()

        # Update status to filled
        t.status = TradeStatus.FILLED
        t.filled_price = 3190
        t.pnl = 100
        db.commit()

        updated = db.query(Trade).filter_by(id="UPD-001").first()
        assert updated.status == TradeStatus.FILLED
        assert updated.pnl == 100
