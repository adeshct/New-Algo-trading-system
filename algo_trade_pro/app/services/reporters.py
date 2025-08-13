import os
from datetime import datetime
import pandas as pd

from app.models.database import get_db_session
from app.models.trade import Trade, TradeStatus
from app.config.settings import get_settings
from app.services.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

def generate_daily_excel_report():
    """Generates a daily Excel report for all completed trades"""
    
    report_dir = os.path.join(settings.REPORT_DIRECTORY, "daily_reports")
    os.makedirs(report_dir, exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    filename = f"trade_report_{today}.xlsx"
    file_path = os.path.join(report_dir, filename)

    with get_db_session() as session:
        try:
            trades = session.query(Trade).filter(Trade.status == TradeStatus.FILLED).all()

            if not trades:
                logger.warning("No filled trades found for report generation.")
                return

            trade_data = []
            for trade in trades:
                trade_data.append({
                    "Trade ID": trade.id,
                    "Symbol": trade.symbol,
                    "Action": trade.side,
                    "Quantity": trade.quantity,
                    "Price": trade.filled_price or trade.price,
                    "Strategy": trade.strategy,
                    "Status": trade.status,
                    "Time": trade.filled_timestamp or trade.timestamp
                })

            df = pd.DataFrame(trade_data)
            df["Time"] = pd.to_datetime(df["Time"])

            # Summary
            total_trades = len(df)
            net_position = df["Quantity"].sum()
            avg_price = df["Price"].mean()
            total_volume = df["Quantity"].sum()
            buy_volume = df[df["Action"] == "BUY"]["Quantity"].sum()
            sell_volume = df[df["Action"] == "SELL"]["Quantity"].sum()

            summary_data = {
                "Total Trades": [total_trades],
                "Buy Volume": [buy_volume],
                "Sell Volume": [sell_volume],
                "Net Position": [net_position],
                "Average Price": [avg_price],
                "Total Volume": [total_volume]
            }
            summary_df = pd.DataFrame(summary_data)

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Write detailed trades
                df.to_excel(writer, sheet_name="Trade Details", index=False)
                
                # Write summary
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

            logger.info(f"Daily Excel report generated: {file_path}")

        except Exception as e:
            logger.error(f"Error generating Excel report: {e}")
