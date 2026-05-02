"""EMA + MACD + RSI confluence with ATR-based stops."""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from .types import Signal


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
            reason=f"Confluence: uptrend + MACD cross + RSI={last['rsi']:.1f}",
        )

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
            reason=f"Confluence: downtrend + MACD cross + RSI={last['rsi']:.1f}",
        )

    return None
