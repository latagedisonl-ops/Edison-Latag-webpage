"""Alpaca broker adapter. Stocks + ETFs, paper or live."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from .config import Config
from .strategy import Signal


_TF_MAP = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}


class Broker:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.trading = TradingClient(cfg.alpaca_key, cfg.alpaca_secret, paper=cfg.is_paper)
        self.data = StockHistoricalDataClient(cfg.alpaca_key, cfg.alpaca_secret)

    # ---- account / positions ----
    def equity(self) -> float:
        acct = self.trading.get_account()
        return float(acct.equity)

    def open_positions(self) -> list:
        return self.trading.get_all_positions()

    def market_open(self) -> bool:
        return bool(self.trading.get_clock().is_open)

    # ---- bars ----
    def bars(self, symbol: str, lookback_bars: int = 200) -> pd.DataFrame:
        tf = _TF_MAP.get(self.cfg.timeframe, _TF_MAP["15Min"])
        # Fetch a generous window; intraday timeframes need more recent data
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start, end=end)
        resp = self.data.get_stock_bars(req)
        if symbol not in resp.data or not resp.data[symbol]:
            return pd.DataFrame()
        rows = [
            {
                "time": b.timestamp,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in resp.data[symbol]
        ]
        df = pd.DataFrame(rows).set_index("time").sort_index()
        return df.tail(lookback_bars)

    # ---- orders ----
    def submit_bracket(self, sig: Signal, qty: int) -> str:
        """Submit a bracket order: market entry + stop loss + take profit. Returns order id."""
        side = OrderSide.BUY if sig.side == "long" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=sig.symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            order_class="bracket",
            take_profit=TakeProfitRequest(limit_price=round(sig.take_profit, 2)),
            stop_loss=StopLossRequest(stop_price=round(sig.stop, 2)),
        )
        order = self.trading.submit_order(req)
        return str(order.id)

    def close_all(self) -> None:
        self.trading.close_all_positions(cancel_orders=True)
