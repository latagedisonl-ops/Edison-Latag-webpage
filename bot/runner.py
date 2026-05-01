"""Main loop: scan watchlist on a schedule, emit signals, execute approved trades."""
from __future__ import annotations

import asyncio
import signal as _signal

from loguru import logger

from . import risk, strategy
from .broker import Broker
from .config import Config
from .telegram_iface import PendingTrade, TelegramIface


class Runner:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.broker = Broker(cfg)
        self.tg = TelegramIface(cfg)
        self._scanning = False
        self._stop = asyncio.Event()
        self._signaled_today: set[str] = set()

    async def _approve(self, pending: PendingTrade) -> str:
        try:
            order_id = await asyncio.to_thread(
                self.broker.submit_bracket, pending.sig, pending.qty
            )
            return f"order {order_id[:8]}"
        except Exception as e:
            logger.exception("submit failed")
            return f"ERROR: {e}"

    async def _status(self) -> str:
        try:
            eq = await asyncio.to_thread(self.broker.equity)
            poss = await asyncio.to_thread(self.broker.open_positions)
            ds = risk.get_daily_state(eq)
            lines = [
                f"Equity: ${eq:,.2f}",
                f"Day P&L: ${ds.realized_pnl:,.2f} (start ${ds.starting_equity:,.2f})",
                f"Halted: {ds.halted}",
                f"Positions ({len(poss)}):",
            ]
            for p in poss:
                lines.append(f"  {p.symbol} {p.qty} @ {p.avg_entry_price} "
                             f"P&L ${float(p.unrealized_pl):,.2f}")
            return "\n".join(lines)
        except Exception as e:
            return f"status error: {e}"

    async def _halt(self) -> str:
        risk.set_halted(True)
        return "Halted. No new entries until /resume."

    async def _resume(self) -> str:
        risk.set_halted(False)
        return "Resumed."

    async def _closeall(self) -> str:
        await asyncio.to_thread(self.broker.close_all)
        return "All positions closing."

    async def _scan_once(self) -> None:
        if self._scanning:
            return
        self._scanning = True
        try:
            if not await asyncio.to_thread(self.broker.market_open):
                return
            equity = await asyncio.to_thread(self.broker.equity)
            poss = await asyncio.to_thread(self.broker.open_positions)
            held = {p.symbol for p in poss}

            ok, reason = risk.can_open_new(self.cfg, equity, len(poss))
            if not ok:
                logger.info(f"skip scan: {reason}")
                return

            for symbol in self.cfg.watchlist:
                if symbol in held or symbol in self._signaled_today:
                    continue
                try:
                    bars = await asyncio.to_thread(self.broker.bars, symbol)
                    if bars.empty:
                        continue
                    sig = strategy.evaluate(symbol, bars)
                    if not sig or sig.rr < 1.5:
                        continue
                    qty = risk.position_size(self.cfg, equity, sig)
                    if qty <= 0:
                        continue
                    self._signaled_today.add(symbol)
                    await self.tg.send_signal(PendingTrade(sig=sig, qty=qty))
                except Exception as e:
                    logger.exception(f"scan {symbol}: {e}")
        finally:
            self._scanning = False

    async def run(self) -> None:
        self.tg.wire(
            on_approve=self._approve,
            status_cb=self._status,
            halt_cb=self._halt,
            resume_cb=self._resume,
            closeall_cb=self._closeall,
        )
        await self.tg.start()
        await self.tg.notify(
            f"Bot started. Mode={self.cfg.execution_mode} Paper={self.cfg.is_paper} "
            f"Watchlist={','.join(self.cfg.watchlist)}"
        )

        loop = asyncio.get_running_loop()
        for s in (_signal.SIGINT, _signal.SIGTERM):
            loop.add_signal_handler(s, self._stop.set)

        try:
            while not self._stop.is_set():
                try:
                    await self._scan_once()
                except Exception as e:
                    logger.exception(f"scan loop: {e}")
                # Scan cadence: align to timeframe, but cap at 60s for responsiveness on small TFs
                await asyncio.wait_for(self._stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass
        finally:
            await self.tg.notify("Bot stopping.")
            await self.tg.stop()


def main() -> None:
    cfg = Config.load()
    logger.add("bot.log", rotation="10 MB", retention=5)
    asyncio.run(Runner(cfg).run())


if __name__ == "__main__":
    main()
