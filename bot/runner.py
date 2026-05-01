"""Main loop: scan watchlist on a schedule, emit signals, execute approved trades."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from loguru import logger

from . import risk, strategy
from .broker import Broker
from .config import Config
from .settings import SettingsStore
from .telegram_iface import PendingTrade, TelegramIface


@dataclass
class SignalRecord:
    ts: float
    symbol: str
    side: str
    entry: float
    stop: float
    take_profit: float
    rr: float
    qty: int
    status: str  # 'pending' | 'approved' | 'rejected' | 'auto' | 'error'
    detail: str = ""


class Runner:
    def __init__(self, cfg: Config, settings_store: SettingsStore):
        self.cfg = cfg
        self.settings = settings_store
        self.broker = Broker(cfg)
        self.tg = TelegramIface(cfg, settings_store)
        self._scanning = False
        self._stop = asyncio.Event()
        self._signaled_today: set[str] = set()
        self._signal_history: deque[SignalRecord] = deque(maxlen=100)
        self._task: asyncio.Task | None = None
        self._last_scan_ts: float = 0.0

    # ---- Telegram callbacks ----
    async def _approve(self, pending: PendingTrade) -> str:
        try:
            order_id = await asyncio.to_thread(
                self.broker.submit_bracket, pending.sig, pending.qty
            )
            self._record_status(pending, "approved", f"order {order_id[:8]}")
            return f"order {order_id[:8]}"
        except Exception as e:
            logger.exception("submit failed")
            self._record_status(pending, "error", str(e))
            return f"ERROR: {e}"

    async def _status(self) -> str:
        try:
            data = await self.status_payload()
            lines = [
                f"Equity: ${data['equity']:,.2f}",
                f"Day P&L: ${data['day_pnl']:,.2f} (start ${data['day_start_equity']:,.2f})",
                f"Halted: {data['halted']}",
                f"Positions ({len(data['positions'])}):",
            ]
            for p in data["positions"]:
                lines.append(
                    f"  {p['symbol']} {p['qty']} @ {p['avg_entry']:.2f} "
                    f"P&L ${p['unrealized_pl']:,.2f}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"status error: {e}"

    async def _halt(self) -> str:
        risk.set_halted(True)
        return "Halted. No new entries until resume."

    async def _resume(self) -> str:
        risk.set_halted(False)
        return "Resumed."

    async def _closeall(self) -> str:
        await asyncio.to_thread(self.broker.close_all)
        return "All positions closing."

    # ---- web payload ----
    async def status_payload(self) -> dict[str, Any]:
        eq = await asyncio.to_thread(self.broker.equity)
        poss = await asyncio.to_thread(self.broker.open_positions)
        market_open = await asyncio.to_thread(self.broker.market_open)
        ds = risk.get_daily_state(eq)
        return {
            "equity": eq,
            "day_pnl": ds.realized_pnl,
            "day_start_equity": ds.starting_equity,
            "halted": ds.halted,
            "market_open": market_open,
            "is_paper": self.cfg.is_paper,
            "execution_mode": self.settings.get().execution_mode,
            "last_scan_ts": self._last_scan_ts,
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price) if p.current_price else 0.0,
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else 0.0,
                }
                for p in poss
            ],
        }

    def signal_history(self) -> list[dict[str, Any]]:
        return [asdict(r) for r in reversed(self._signal_history)]

    # ---- scan ----
    def _record_signal(self, sig, qty: int, status: str, detail: str = "") -> None:
        self._signal_history.append(
            SignalRecord(
                ts=time.time(),
                symbol=sig.symbol,
                side=sig.side,
                entry=sig.entry,
                stop=sig.stop,
                take_profit=sig.take_profit,
                rr=sig.rr,
                qty=qty,
                status=status,
                detail=detail,
            )
        )

    def _record_status(self, pending: PendingTrade, status: str, detail: str = "") -> None:
        # update most recent matching signal record's status
        for rec in reversed(self._signal_history):
            if rec.symbol == pending.sig.symbol and rec.status == "pending":
                rec.status = status
                rec.detail = detail
                return

    async def _scan_once(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        try:
            self._last_scan_ts = time.time()
            if not await asyncio.to_thread(self.broker.market_open):
                return
            equity = await asyncio.to_thread(self.broker.equity)
            poss = await asyncio.to_thread(self.broker.open_positions)
            held = {p.symbol for p in poss}
            s = self.settings.get()

            ok, reason = risk.can_open_new(s, equity, len(poss))
            if not ok:
                logger.info(f"skip scan: {reason}")
                return

            for symbol in s.watchlist:
                if symbol in held or symbol in self._signaled_today:
                    continue
                try:
                    bars = await asyncio.to_thread(self.broker.bars, symbol)
                    if bars.empty:
                        continue
                    sig = strategy.evaluate(symbol, bars, rr_target=s.rr_target)
                    if not sig or sig.rr < 1.5:
                        continue
                    qty = risk.position_size(s, equity, sig)
                    if qty <= 0:
                        continue
                    self._signaled_today.add(symbol)
                    status = "auto" if s.execution_mode == "auto" else "pending"
                    self._record_signal(sig, qty, status)
                    await self.tg.send_signal(PendingTrade(sig=sig, qty=qty))
                except Exception as e:
                    logger.exception(f"scan {symbol}: {e}")
        finally:
            self._scanning = False

    # ---- lifecycle ----
    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        self.tg.wire(
            on_approve=self._approve,
            status_cb=self._status,
            halt_cb=self._halt,
            resume_cb=self._resume,
            closeall_cb=self._closeall,
        )
        await self.tg.start()
        s = self.settings.get()
        await self.tg.notify(
            f"Bot started. Mode={s.execution_mode} Paper={self.cfg.is_paper} "
            f"Risk={s.risk_per_trade*100:.2f}% Watchlist={','.join(s.watchlist)}"
        )

        try:
            while not self._stop.is_set():
                try:
                    await self._scan_once()
                except Exception as e:
                    logger.exception(f"scan loop: {e}")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
        finally:
            try:
                await self.tg.notify("Bot stopping.")
            except Exception:
                pass
            await self.tg.stop()
