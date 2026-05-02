from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["long", "short"]


@dataclass
class Signal:
    symbol: str
    side: Side
    entry: float
    stop: float
    take_profit: float
    reason: str

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_share(self) -> float:
        return abs(self.take_profit - self.entry)

    @property
    def rr(self) -> float:
        if self.risk_per_share == 0:
            return 0.0
        return self.reward_per_share / self.risk_per_share
