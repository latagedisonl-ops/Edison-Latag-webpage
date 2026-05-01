"""Risk management. The bot's most important module.

Rules enforced:
1. Per-trade risk capped at config.risk_per_trade of equity.
2. Position size = (equity * risk_pct) / per-share-risk.
3. Max concurrent open positions.
4. Daily loss circuit breaker — bot halts new entries if hit.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

from .config import Config
from .strategy import Signal

STATE_FILE = Path("state.json")


@dataclass
class DailyState:
    day: str
    starting_equity: float
    realized_pnl: float = 0.0
    halted: bool = False


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_daily_state(equity: float) -> DailyState:
    state = _load_state()
    today = date.today().isoformat()
    if state.get("day") != today:
        ds = DailyState(day=today, starting_equity=equity)
        _save_state(asdict(ds))
        return ds
    return DailyState(**state)


def update_daily_pnl(realized_delta: float) -> DailyState:
    state = _load_state()
    state["realized_pnl"] = state.get("realized_pnl", 0.0) + realized_delta
    _save_state(state)
    return DailyState(**state)


def set_halted(halted: bool) -> None:
    state = _load_state()
    state["halted"] = halted
    _save_state(state)


def position_size(cfg: Config, equity: float, sig: Signal) -> int:
    """Return integer share quantity, or 0 if trade is invalid."""
    if sig.risk_per_share <= 0:
        return 0
    dollar_risk = equity * cfg.risk_per_trade
    qty = math.floor(dollar_risk / sig.risk_per_share)
    # Cap notional to available buying power proxy: 25% of equity per single position
    max_notional = equity * 0.25
    qty = min(qty, math.floor(max_notional / sig.entry))
    return max(qty, 0)


def can_open_new(cfg: Config, equity: float, open_positions: int) -> tuple[bool, str]:
    if open_positions >= cfg.max_open_positions:
        return False, f"Max open positions reached ({open_positions}/{cfg.max_open_positions})"

    ds = get_daily_state(equity)
    if ds.halted:
        return False, "Bot halted (daily loss limit hit). Reset with /resume."
    loss_limit = -cfg.max_daily_loss * ds.starting_equity
    if ds.realized_pnl <= loss_limit:
        set_halted(True)
        return False, f"Daily loss limit hit: {ds.realized_pnl:.2f} <= {loss_limit:.2f}"
    return True, "OK"
