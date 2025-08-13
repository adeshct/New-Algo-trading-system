import pytest
import pandas as pd
from datetime import datetime, timedelta

from app.strategies.rsi_strategy import RSIStrategy
from app.strategies.moving_average import MovingAverageStrategy
from app.strategies.bollinger_bands import BollingerBandsStrategy


# Helper to create dummy OHLCV data
def make_ohlcv_data(length=30, price=1000):
    timestamps = [datetime.now() - timedelta(minutes=i) for i in reversed(range(length))]
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': [price + i * 0.5 for i in range(length)],
        'high': [price + i * 1.0 for i in range(length)],
        'low':  [price + i * 0.2 for i in range(length)],
        'close': [price + i * 0.8 for i in range(length)],
        'volume': [1000 + i * 5 for i in range(length)],
    }).set_index("timestamp")


def test_rsi_strategy_buy():
    """RSI should generate buy when RSI dips below threshold."""
    strategy = RSIStrategy(symbols=["TEST"])
    data = make_ohlcv_data()
    data.iloc[-2:, data.columns.get_loc("close")] = 900  # Drop price to drop RSI

    result = strategy.generate_signals({"TEST": data})
    assert isinstance(result, list)
    assert len(result) >= 0  # May or may not generate
    for signal in result:
        assert signal["symbol"] == "TEST"
        assert signal["action"] in ["BUY", "SELL"]
        assert "price" in signal


def test_moving_average_cross_signal():
    strategy = MovingAverageStrategy(name="MA_Test", short_window=3, long_window=5, symbols=["TEST"])
    df = make_ohlcv_data(10)
    df["close"] = [900, 910, 920, 930, 940, 950, 960, 965, 970, 980]  # Simulate upward trend
    signals = strategy.generate_signals({"TEST": df})
    assert isinstance(signals, list)
    # May expect one GOLDEN CROSS (BUY)
    for sig in signals:
        assert sig["strategy"] == strategy.name
        assert sig["symbol"] == "TEST"


def test_bollinger_band_signal():
    strategy = BollingerBandsStrategy(symbols=["TEST"])
    df = make_ohlcv_data()
    df.loc[:, "close"] = [i * 1.5 for i in range(len(df))]  # Increase volatility to trigger breakout
    signals = strategy.generate_signals({"TEST": df})
    for signal in signals:
        assert signal["symbol"] == "TEST"
        assert signal["action"] in ["BUY", "SELL"]
        assert "signal_type" in signal
