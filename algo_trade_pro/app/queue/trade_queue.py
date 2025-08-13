"""
app/queue/trade_queue.py

Thread-safe queues for trade signal and execution processing between StrategyEngine, TradeExecutor, and RiskManager.
"""

from queue import Queue

# Queue for strategy-generated signals waiting to be executed
trade_signal_queue = Queue(maxsize=1000)

# Optional: queue to track completed trades (can be used for reporting, monitoring, audit)
trade_execution_queue = Queue(maxsize=1000)

# Example usage:
# trade_signal_queue.put(signal_dict)
# signal = trade_signal_queue.get()
