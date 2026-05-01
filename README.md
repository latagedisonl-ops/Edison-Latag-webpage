# Trading Signal Bot (Stocks) + Telegram

A realistic, risk-managed trading bot that scans a stock watchlist for
multi-confluence technical signals (EMA trend + MACD cross + RSI), sizes
positions by ATR-based stop distance, and sends alerts to Telegram.

## ⚠️ Read this first

- **No bot wins 90–100% of trades.** Anyone selling that is lying.
  Profitable systems have ~40–60% winrate with reward:risk ≥ 1.5:1.
- This bot defaults to **paper trading** and **manual approval** mode.
  You approve every trade from Telegram. Don't change that until you've
  watched it for weeks and run a backtest.
- Stocks only via Alpaca. Crypto/forex/futures are not in scope —
  every market needs different microstructure, hours, fees, and risk
  rules. Adding them properly is a separate project.
- Risk only money you can lose. Backtest before live. Past performance
  doesn't predict future results.

## What it does

- Scans your watchlist every minute during market hours.
- A trade signal requires **all** of:
  - EMA(20) above/below EMA(50) — trend filter
  - MACD line crossing the signal line on the latest bar — momentum
  - RSI(14) in 50–70 (long) or 30–50 (short) — not overbought/oversold
- Stop = 1.5 × ATR(14). Take-profit = 2× the risk distance (R:R ≥ 2).
- Position size = (equity × `RISK_PER_TRADE`) / per-share-risk.
- Daily loss circuit breaker — auto-halt if losses exceed `MAX_DAILY_LOSS`.
- Telegram approval buttons for every signal in `manual` mode.

See **[SETUP.md](SETUP.md)** for the full step-by-step tutorial:
account creation → API keys → install → run.

## Commands (Telegram)

| command     | what it does                              |
|-------------|-------------------------------------------|
| `/start`    | Greeting + mode info                      |
| `/status`   | Equity, day P&L, open positions           |
| `/halt`     | Stop new entries                          |
| `/resume`   | Resume after halt                         |
| `/closeall` | Flatten every open position immediately   |

## Project layout

```
bot/
  config.py         env loading
  strategy.py       indicators + signal logic
  risk.py           position sizing + circuit breaker
  broker.py         Alpaca adapter (data + orders)
  telegram_iface.py Telegram bot, signal cards w/ approve/reject
  runner.py         async main loop
run.py              entrypoint
requirements.txt
.env.example
SETUP.md
```
