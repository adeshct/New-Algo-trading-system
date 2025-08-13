"""
app/services/pnl_calculator.py

Provides functions to calculate profit and loss (PnL) for trades and positions.
"""

from typing import Union
from app.models.trade import Trade, TradeStatus
from app.models.position import Position
from app.models.database import get_db_session

    
class PnLCalculator:
    """
    Utility class to calculate P&L at trade and position level.
    """

    def __init__(self, brokerage_perc: float = 0.03):
        """
        :param brokerage_perc: Broker fee in percentage (0.03% default)
        """
        self.brokerage_percent = brokerage_perc / 100

    def calculate_trade_pnl(self, trade: Trade, exit_price: float) -> float:
        """
        Calculate P&L of an individual trade that has been exited.

        :param trade: Trade model instance
        :param exit_price: Price at which trade was closed
        :return: net P&L after estimated brokerage/deductions
        """
        if not trade or trade.quantity <= 0:
            return 0.0

        entry_price = trade.filled_price or trade.price
        quantity = trade.quantity

        if trade.side == "BUY":
            gross_pnl = (exit_price - entry_price) * quantity
        elif trade.side == "SELL":
            gross_pnl = (entry_price - exit_price) * quantity
        else:
            return 0.0

        # Brokerage deduction (both for entry and exit)
        brokerage = (entry_price + exit_price) * quantity * self.brokerage_percent
        net_pnl = gross_pnl - brokerage
        return round(net_pnl, 2)

    def calculate_position_pnl(self, position: Position, current_price: float) -> float:
        """
        Calculate real-time floating P&L of an open position.

        :param position: Position model instance
        :param current_price: Latest market price of the symbol
        :return: net unrealized P&L
        """
        if not position or position.quantity == 0:
            return 0.0

        direction = 1 if position.quantity > 0 else -1
        effective_qty = abs(position.quantity)

        price_diff = (current_price - position.avg_price) * direction
        gross_pnl = price_diff * effective_qty

        # Apply brokerage on both legs
        brokerage = (current_price + position.avg_price) * effective_qty * self.brokerage_percent
        net_pnl = gross_pnl - brokerage
        return round(net_pnl, 2)
    
    def get_realtime_strategy_pnl(strategy_name: str) -> dict:
        with get_db_session() as db:
            trades = db.query(Trade).filter(Trade.strategy == strategy_name).all()
            # Realized P&L from closed/exited trades
            realized = sum((t.pnl or 0) for t in trades if t.status in [TradeStatus.FILLED, TradeStatus.EXITED])
            # Unrealized P&L from open positions (if using a Position model)
            positions = db.query(Position).filter(Position.strategy == strategy_name).all()
            unrealized = sum((p.pnl or 0) for p in positions)
            return {
                "strategy": strategy_name,
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": realized + unrealized
            }