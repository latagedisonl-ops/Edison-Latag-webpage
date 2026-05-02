"""Mutable runtime settings, persisted to settings.json.

Credentials (API keys, telegram token, chat id) stay in env via Config —
they should not be editable from the web UI. Trading parameters live here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import Config

SETTINGS_FILE = Path("settings.json")
VALID_TIMEFRAMES = ("1Min", "5Min", "15Min", "1Hour", "1Day")
VALID_MODES = ("manual", "auto")
VALID_STRATEGIES = ("confluence", "smc")


@dataclass
class RuntimeSettings:
    watchlist: list[str] = field(default_factory=list)
    timeframe: str = "15Min"
    risk_per_trade: float = 0.01
    max_open_positions: int = 5
    max_daily_loss: float = 0.03
    execution_mode: str = "manual"
    rr_target: float = 2.0
    strategy: str = "confluence"


def _coerce(field_name: str, value: Any) -> Any:
    if field_name == "risk_per_trade":
        v = float(value)
        if not (0 < v <= 0.10):
            raise ValueError("risk_per_trade must be in (0, 0.10]")
        return v
    if field_name == "max_daily_loss":
        v = float(value)
        if not (0 < v <= 0.50):
            raise ValueError("max_daily_loss must be in (0, 0.50]")
        return v
    if field_name == "rr_target":
        v = float(value)
        if not (1.0 <= v <= 10.0):
            raise ValueError("rr_target must be in [1.0, 10.0]")
        return v
    if field_name == "max_open_positions":
        v = int(value)
        if not (1 <= v <= 50):
            raise ValueError("max_open_positions must be in [1, 50]")
        return v
    if field_name == "timeframe":
        if value not in VALID_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {VALID_TIMEFRAMES}")
        return value
    if field_name == "execution_mode":
        v = str(value).lower()
        if v not in VALID_MODES:
            raise ValueError(f"execution_mode must be one of {VALID_MODES}")
        return v
    if field_name == "strategy":
        v = str(value).lower()
        if v not in VALID_STRATEGIES:
            raise ValueError(f"strategy must be one of {VALID_STRATEGIES}")
        return v
    if field_name == "watchlist":
        if isinstance(value, str):
            items = [s.strip().upper() for s in value.split(",") if s.strip()]
        elif isinstance(value, list):
            items = [str(s).strip().upper() for s in value if str(s).strip()]
        else:
            raise ValueError("watchlist must be list or comma-separated string")
        if not items:
            raise ValueError("watchlist cannot be empty")
        return items
    raise ValueError(f"unknown setting: {field_name}")


class SettingsStore:
    def __init__(self, cfg: Config):
        self._defaults = RuntimeSettings(
            watchlist=list(cfg.watchlist),
            timeframe=cfg.timeframe,
            risk_per_trade=cfg.risk_per_trade,
            max_open_positions=cfg.max_open_positions,
            max_daily_loss=cfg.max_daily_loss,
            execution_mode=cfg.execution_mode,
        )
        self._settings = self._load()

    def _load(self) -> RuntimeSettings:
        merged = asdict(self._defaults)
        if SETTINGS_FILE.exists():
            try:
                merged.update(json.loads(SETTINGS_FILE.read_text()))
            except Exception:
                pass
        return RuntimeSettings(**merged)

    def get(self) -> RuntimeSettings:
        return self._settings

    def as_dict(self) -> dict[str, Any]:
        return asdict(self._settings)

    def update(self, patch: dict[str, Any]) -> RuntimeSettings:
        for k, v in patch.items():
            setattr(self._settings, k, _coerce(k, v))
        SETTINGS_FILE.write_text(json.dumps(asdict(self._settings), indent=2))
        return self._settings
