"""Strategy dispatcher.

Implementations live in bot/strategies/<name>.py and share the Signal type
from bot/strategies/types.py. Picked at runtime via SettingsStore.strategy.
"""
from __future__ import annotations

import pandas as pd

from .strategies.confluence import evaluate as _confluence
from .strategies.smc import evaluate as _smc
from .strategies.types import Side, Signal

__all__ = ["Signal", "Side", "evaluate", "STRATEGIES"]

STRATEGIES = {
    "confluence": _confluence,
    "smc": _smc,
}


def evaluate(
    symbol: str,
    bars: pd.DataFrame,
    *,
    strategy_name: str = "confluence",
    rr_target: float = 2.0,
) -> Signal | None:
    fn = STRATEGIES.get(strategy_name, _confluence)
    return fn(symbol, bars, rr_target=rr_target)
