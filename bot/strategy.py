"""Multi-confluence technical signal generator.

A trade is taken only when EMA trend, MACD momentum, and RSI all agree.
ATR sets stop-loss distance; reward is 2x risk (2:1 R:R minimum).
This is NOT a holy grail — it has losing trades. Profit comes from R:R + discipline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import pandas_ta as ta

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


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ta.ema(df["close"], length=20)
    df["ema_slow"] = ta.ema(df["close"], length=50)
    df["rsi"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd["MACD_12_26_9"]
    df["macd_signal"] = macd["MACDs_12_26_9"]
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    return df


def evaluate(symbol: str, bars: pd.DataFrame, rr_target: float = 2.0) -> Signal | None:
    """Return a Signal if confluence conditions are met, else None.

    bars must have columns: open, high, low, close, volume — indexed by time, ascending.
    """
    if len(bars) < 60:
        return None

    df = _add_indicators(bars)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if any(pd.isna(last[c]) for c in ("ema_fast", "ema_slow", "rsi", "macd", "macd_signal", "atr")):
        return None

    price = float(last["close"])
    atr = float(last["atr"])
    if atr <= 0:
        return None

    # LONG: uptrend (EMA20 > EMA50), MACD bullish cross or above signal, RSI 50-70 (momentum, not overbought)
    long_trend = last["ema_fast"] > last["ema_slow"]
    long_macd = last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]
    long_rsi = 50 < last["rsi"] < 70

    if long_trend and long_macd and long_rsi:
        stop = price - 1.5 * atr
        tp = price + rr_target * (price - stop)
        return Signal(
            symbol=symbol,
            side="long",
            entry=price,
            stop=round(stop, 2),
            take_profit=round(tp, 2),
            reason=f"Uptrend + MACD cross + RSI={last['rsi']:.1f}",
        )

    # SHORT: downtrend, MACD bearish cross, RSI 30-50
    short_trend = last["ema_fast"] < last["ema_slow"]
    short_macd = last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"]
    short_rsi = 30 < last["rsi"] < 50

    if short_trend and short_macd and short_rsi:
        stop = price + 1.5 * atr
        tp = price - rr_target * (stop - price)
        return Signal(
            symbol=symbol,
            side="short",
            entry=price,
            stop=round(stop, 2),
            take_profit=round(tp, 2),
            reason=f"Downtrend + MACD cross + RSI={last['rsi']:.1f}",
        )

    return None
