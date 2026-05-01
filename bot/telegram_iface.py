"""Telegram interface: signal alerts, manual approval, status commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .config import Config
from .settings import SettingsStore
from .strategy import Signal


@dataclass
class PendingTrade:
    sig: Signal
    qty: int


class TelegramIface:
    def __init__(self, cfg: Config, settings_store: SettingsStore):
        self.cfg = cfg
        self.settings = settings_store
        self.app = Application.builder().token(cfg.telegram_token).build()
        self._pending: dict[str, PendingTrade] = {}
        self._on_approve: Callable[[PendingTrade], Awaitable[str]] | None = None
        self._status_cb: Callable[[], Awaitable[str]] | None = None
        self._halt_cb: Callable[[], Awaitable[str]] | None = None
        self._resume_cb: Callable[[], Awaitable[str]] | None = None
        self._closeall_cb: Callable[[], Awaitable[str]] | None = None

    def wire(
        self,
        on_approve: Callable[[PendingTrade], Awaitable[str]],
        status_cb: Callable[[], Awaitable[str]],
        halt_cb: Callable[[], Awaitable[str]],
        resume_cb: Callable[[], Awaitable[str]],
        closeall_cb: Callable[[], Awaitable[str]],
    ) -> None:
        self._on_approve = on_approve
        self._status_cb = status_cb
        self._halt_cb = halt_cb
        self._resume_cb = resume_cb
        self._closeall_cb = closeall_cb
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("halt", self._cmd_halt))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))
        self.app.add_handler(CommandHandler("closeall", self._cmd_closeall))
        self.app.add_handler(CallbackQueryHandler(self._on_button))

    def _allowed(self, update: Update) -> bool:
        return bool(update.effective_chat) and update.effective_chat.id == self.cfg.telegram_chat_id

    async def _cmd_start(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        if not self._allowed(update):
            return
        s = self.settings.get()
        await update.message.reply_text(
            "Trading bot online.\n"
            "Commands: /status /halt /resume /closeall\n"
            f"Mode: {s.execution_mode} | Paper: {self.cfg.is_paper} | "
            f"Risk: {s.risk_per_trade*100:.2f}%"
        )

    async def _cmd_status(self, update, _):
        if not self._allowed(update) or not self._status_cb:
            return
        await update.message.reply_text(await self._status_cb())

    async def _cmd_halt(self, update, _):
        if not self._allowed(update) or not self._halt_cb:
            return
        await update.message.reply_text(await self._halt_cb())

    async def _cmd_resume(self, update, _):
        if not self._allowed(update) or not self._resume_cb:
            return
        await update.message.reply_text(await self._resume_cb())

    async def _cmd_closeall(self, update, _):
        if not self._allowed(update) or not self._closeall_cb:
            return
        await update.message.reply_text(await self._closeall_cb())

    async def _on_button(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if not self._allowed(update):
            return
        action, _, key = q.data.partition(":")
        pending = self._pending.pop(key, None)
        if not pending:
            await q.edit_message_text(q.message.text + "\n\n(expired)")
            return
        if action == "approve" and self._on_approve:
            result = await self._on_approve(pending)
            await q.edit_message_text(q.message.text + f"\n\nAPPROVED -> {result}")
        else:
            await q.edit_message_text(q.message.text + "\n\nREJECTED")

    async def send_signal(self, pending: PendingTrade) -> None:
        sig = pending.sig
        key = f"{sig.symbol}-{int(sig.entry * 100)}"
        self._pending[key] = pending
        notional = pending.qty * sig.entry
        text = (
            f"SIGNAL: {sig.symbol} {sig.side.upper()}\n"
            f"Entry: {sig.entry:.2f}  Stop: {sig.stop:.2f}  TP: {sig.take_profit:.2f}\n"
            f"R:R = {sig.rr:.2f}\n"
            f"Qty: {pending.qty} (~${notional:,.0f})\n"
            f"Reason: {sig.reason}"
        )
        mode = self.settings.get().execution_mode
        if mode == "manual":
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("Approve", callback_data=f"approve:{key}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{key}"),
            ]])
            await self.app.bot.send_message(self.cfg.telegram_chat_id, text, reply_markup=kb)
        else:
            await self.app.bot.send_message(self.cfg.telegram_chat_id, text + "\n\n(auto-executing)")
            if self._on_approve:
                result = await self._on_approve(pending)
                await self.app.bot.send_message(self.cfg.telegram_chat_id, f"Executed: {result}")

    async def notify(self, text: str) -> None:
        try:
            await self.app.bot.send_message(self.cfg.telegram_chat_id, text)
        except Exception as e:
            logger.exception(f"telegram notify failed: {e}")

    async def start(self) -> None:
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def stop(self) -> None:
        try:
            await self.app.updater.stop()
        except Exception:
            pass
        try:
            await self.app.stop()
        except Exception:
            pass
        try:
            await self.app.shutdown()
        except Exception:
            pass
