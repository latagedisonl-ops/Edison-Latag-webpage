"""Smart Money Concepts (SMC) / ICT-inspired strategy.

A trade requires three things to align:
  1. Bias: most recent Break of Structure (BOS) — close beyond the latest
     confirmed swing high (bullish) or swing low (bearish).
  2. Liquidity sweep: a recent bar wicks past a prior swing low (long setup)
     or swing high (short setup) and closes back through it. Models a
     classic "stop hunt".
  3. Unfilled Fair Value Gap (FVG): a 3-bar imbalance left in the
     direction of the new bias, not yet rebalanced by later price action.

Stop = beyond sweep wick + 0.25 x ATR. Take-profit = next opposing
liquidity (untouched swing high/low) when it offers >= 1.5R, else fall
back to rr_target x risk.

Reality check: SMC is a useful framework, not a crystal ball. It still
loses trades. Backtest before trusting it.
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from .types import Signal

SWING_N = 3            # fractal lookback on each side
FVG_MAX_AGE = 25       # bars old that an FVG can be and still count
SWEEP_WINDOW = 3       # how many recent bars are eligible as the sweep
ATR_BUFFER = 0.25      # multiplier padding the stop past the sweep


def _find_swings(df: pd.DataFrame, n: int = SWING_N):
    highs = df["high"].values
    lows = df["low"].values
    sh: list[tuple[int, float]] = []
    sl: list[tuple[int, float]] = []
    for i in range(n, len(df) - n):
        win_h = highs[i - n : i + n + 1]
        win_l = lows[i - n : i + n + 1]
        if highs[i] == win_h.max() and (win_h == highs[i]).sum() == 1:
            sh.append((i, float(highs[i])))
        if lows[i] == win_l.min() and (win_l == lows[i]).sum() == 1:
            sl.append((i, float(lows[i])))
    return sh, sl


def _last_bos(df: pd.DataFrame, sh: list, sl: list):
    """Return ('bullish'|'bearish', level, break_idx) for the most recent BOS."""
    n = len(df)
    closes = df["close"].values
    candidates = []  # (break_idx, direction, price)
    if sh:
        sh_idx, sh_price = sh[-1]
        for j in range(sh_idx + SWING_N + 1, n):
            if closes[j] > sh_price:
                candidates.append((j, "bullish", sh_price))
                break
    if sl:
        sl_idx, sl_price = sl[-1]
        for j in range(sl_idx + SWING_N + 1, n):
            if closes[j] < sl_price:
                candidates.append((j, "bearish", sl_price))
                break
    if not candidates:
        return None
    return max(candidates, key=lambda t: t[0])


def _bullish_fvg(df: pd.DataFrame, lookback: int = FVG_MAX_AGE):
    n = len(df)
    h, l = df["high"].values, df["low"].values
    for i in range(n - 1, max(n - lookback - 2, 1), -1):
        if i < 2:
            break
        if l[i] > h[i - 2]:
            gap_low, gap_high = float(h[i - 2]), float(l[i])
            filled = any(l[j] <= gap_low for j in range(i + 1, n))
            if not filled:
                return gap_low, gap_high, n - 1 - i
    return None


def _bearish_fvg(df: pd.DataFrame, lookback: int = FVG_MAX_AGE):
    n = len(df)
    h, l = df["high"].values, df["low"].values
    for i in range(n - 1, max(n - lookback - 2, 1), -1):
        if i < 2:
            break
        if h[i] < l[i - 2]:
            gap_low, gap_high = float(h[i]), float(l[i - 2])
            filled = any(h[j] >= gap_high for j in range(i + 1, n))
            if not filled:
                return gap_low, gap_high, n - 1 - i
    return None


def _bullish_sweep(df: pd.DataFrame, sl: list, window: int = SWEEP_WINDOW):
    n = len(df)
    eligible = [(i, p) for i, p in sl if i <= n - window - 1]
    if not eligible:
        return None
    target_idx, target_price = eligible[-1]
    for i in range(n - window, n):
        if df["low"].iloc[i] < target_price and df["close"].iloc[i] > target_price:
            return i, target_price, target_idx
    return None


def _bearish_sweep(df: pd.DataFrame, sh: list, window: int = SWEEP_WINDOW):
    n = len(df)
    eligible = [(i, p) for i, p in sh if i <= n - window - 1]
    if not eligible:
        return None
    target_idx, target_price = eligible[-1]
    for i in range(n - window, n):
        if df["high"].iloc[i] > target_price and df["close"].iloc[i] < target_price:
            return i, target_price, target_idx
    return None


def evaluate(symbol: str, bars: pd.DataFrame, rr_target: float = 2.0) -> Signal | None:
    if len(bars) < 60:
        return None

    df = bars.copy()
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    if pd.isna(df["atr"].iloc[-1]):
        return None
    atr = float(df["atr"].iloc[-1])
    if atr <= 0:
        return None

    sh, sl = _find_swings(df)
    if not sh or not sl:
        return None

    bos = _last_bos(df, sh, sl)
    if not bos:
        return None
    _, direction, _ = bos
    price = float(df["close"].iloc[-1])

    if direction == "bullish":
        sweep = _bullish_sweep(df, sl)
        fvg = _bullish_fvg(df)
        if not (sweep and fvg):
            return None
        sweep_idx, sweep_price, _ = sweep
        gap_low, gap_high, _ = fvg
        # only enter if price has held above (or come back to) the FVG zone
        if price < gap_low:
            return None
        wick_low = float(df["low"].iloc[sweep_idx])
        stop = min(wick_low, gap_low) - ATR_BUFFER * atr
        risk = price - stop
        if risk <= 0:
            return None
        higher_swings = [p for _, p in sh if p > price]
        if higher_swings and (min(higher_swings) - price) / risk >= 1.5:
            tp = min(higher_swings)
        else:
            tp = price + rr_target * risk
        return Signal(
            symbol=symbol,
            side="long",
            entry=price,
            stop=round(stop, 2),
            take_profit=round(tp, 2),
            reason=(
                f"SMC long: bullish BOS + sweep@{sweep_price:.2f} "
                f"+ bullish FVG[{gap_low:.2f}-{gap_high:.2f}]"
            ),
        )

    # bearish
    sweep = _bearish_sweep(df, sh)
    fvg = _bearish_fvg(df)
    if not (sweep and fvg):
        return None
    sweep_idx, sweep_price, _ = sweep
    gap_low, gap_high, _ = fvg
    if price > gap_high:
        return None
    wick_high = float(df["high"].iloc[sweep_idx])
    stop = max(wick_high, gap_high) + ATR_BUFFER * atr
    risk = stop - price
    if risk <= 0:
        return None
    lower_swings = [p for _, p in sl if p < price]
    if lower_swings and (price - max(lower_swings)) / risk >= 1.5:
        tp = max(lower_swings)
    else:
        tp = price - rr_target * risk
    return Signal(
        symbol=symbol,
        side="short",
        entry=price,
        stop=round(stop, 2),
        take_profit=round(tp, 2),
        reason=(
            f"SMC short: bearish BOS + sweep@{sweep_price:.2f} "
            f"+ bearish FVG[{gap_low:.2f}-{gap_high:.2f}]"
        ),
    )
