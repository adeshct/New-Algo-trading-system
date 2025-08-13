from typing import Dict
from app.strategies.base import BaseStrategy

# Global strategy registry
STRATEGY_REGISTRY: Dict[str, BaseStrategy] = {}

def register_strategy(strategy: BaseStrategy):
    """Register a strategy in the global registry."""
    STRATEGY_REGISTRY[strategy.name] = strategy

def get_strategy(name: str) -> BaseStrategy:
    """Get a strategy by name."""
    return STRATEGY_REGISTRY.get(name)

def get_all_strategies() -> Dict[str, BaseStrategy]:
    """Get all registered strategies."""
    return STRATEGY_REGISTRY.copy()