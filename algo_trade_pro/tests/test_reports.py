import os
import pytest
from datetime import datetime
from pathlib import Path
import pandas as pd

from app.services import reporters
from app.models.database import get_db_session, Base, engine
from app.models.trade import Trade, TradeStatus
from app.config.settings import get_settings
from app.models.logs import SystemLog

settings = get_settings()

# -------------------------------------------------
# Test Setup: Fixtures & DB prep
# -------------------------------------------------

@pytest.fixture(autouse=True)
def setup_database():
    # Create test tables
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown: Drop tables after test
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_trades():
    now = datetime.utcnow()
    trade1 = Trade(
        id="trade-001",
        symbol="INFY",
        side="BUY",
        quantity=10,
        price=1450.0,
        filled_price=1465.0,
        strategy="RSI_MeanReversion",
        status=TradeStatus.FILLED,
        timestamp=now,
        filled_timestamp=now,
        pnl=150.0
    )
    trade2 = Trade(
        id="trade-002",
        symbol="TCS",
        side="SELL",
        quantity=5,
        price=3200.0,
        filled_price=3180.0,
        strategy="MA_CrossOver",
        status=TradeStatus.FILLED,
        timestamp=now,
        filled_timestamp=now,
        pnl=100.0
    )

    with get_db_session() as db:
        db.add_all([trade1, trade2])
        db.commit()
    return [trade1, trade2]

# -------------------------------------------------
# Tests
# -------------------------------------------------

def test_generate_excel_report(mock_trades):
    report_folder = Path(settings.REPORT_DIRECTORY) / "daily_reports"
    for f in report_folder.glob("trade_report_*.xlsx"):
        f.unlink()  # Cleanup any previous report for test

    reporters.generate_daily_excel_report()

    # Verify file exists
    date_str = datetime.today().strftime("%Y-%m-%d")
    expected = report_folder / f"trade_report_{date_str}.xlsx"
    assert expected.exists(), "Report file was not generated"

    # Optionally: read back content
    df = pd.read_excel(expected, sheet_name="Trade Details")
    assert not df.empty
    assert "Symbol" in df.columns

def test_summary_table_logic(mock_trades):
    with get_db_session() as db:
        trades = db.query(Trade).all()
        assert len(trades) == 2

        pnl_total = sum(t.pnl for t in trades)
        assert pnl_total == 250.0

        # Check strategy-based grouping manually
        pnl_by_strategy = {t.strategy: t.pnl for t in trades}
        assert pnl_by_strategy["RSI_MeanReversion"] == 150.0
        assert pnl_by_strategy["MA_CrossOver"] == 100.0

def test_generate_report_with_no_trades():
    with get_db_session() as db:
        db.query(Trade).delete()
        db.commit()

    # Should not crash, but log a warning
    reporters.generate_daily_excel_report()

    # File might not be generated if no trades
    date_str = datetime.today().strftime("%Y-%m-%d")
    path = Path(settings.REPORT_DIRECTORY) / "daily_reports" / f"trade_report_{date_str}.xlsx"
    assert not path.exists() or path.stat().st_size == 0
