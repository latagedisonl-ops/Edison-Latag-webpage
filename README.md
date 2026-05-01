# Trading Signal Bot — Web Dashboard + Telegram

A risk-managed stock trading bot with two control surfaces:

- **Web dashboard** at `http://localhost:8787` — live equity, open positions,
  recent signals, **adjustable settings (risk per trade, watchlist, mode,
  R:R, daily-loss cap, etc.)**, embedded tutorial, and log viewer.
- **Telegram bot** — push notifications for signals with **Approve / Reject**
  buttons, plus `/status`, `/halt`, `/resume`, `/closeall` commands.

The dashboard and the bot run in the same process. Settings changed in the UI
are persisted to `settings.json` and applied on the next scan.

## ⚠️ Honest expectations

- **No bot wins 90–100% of trades.** Real systems sit at 40–60% winrate;
  profitability comes from reward:risk and discipline, not winrate.
- **Paper-trade by default.** Set `ALPACA_BASE_URL` to the paper endpoint
  until you've watched the bot for weeks.
- **Manual execution mode by default.** Every trade requires your tap on
  Telegram. Switch to `auto` only after backtesting.

## What the strategy does

A trade fires only when **all three** confluence checks agree:

- EMA(20) above/below EMA(50) — trend filter
- MACD line crossing the signal line on the latest bar — momentum trigger
- RSI(14) in 50–70 (long) or 30–50 (short) — not over-extended

Stop = 1.5 × ATR(14). Take-profit = `R:R target` × stop distance (default 2.0).
Position size = (equity × `risk_per_trade`) / per-share-risk, capped at 25%
notional per position. A daily-loss circuit breaker auto-halts new entries.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env       # fill in keys
python run.py
```

Open <http://127.0.0.1:8787>. The first time, the page prompts for an
**X-Auth-Token** — leave it blank if running locally without
`WEB_AUTH_TOKEN`, or paste the token printed in the startup log.

For the full tutorial (Alpaca account, Telegram bot, going live) read
**[SETUP.md](SETUP.md)** — it's also rendered inside the dashboard's
**Tutorial** tab.

## Settings you can change live in the UI

| setting              | range            | what it does                                            |
|----------------------|------------------|---------------------------------------------------------|
| `risk_per_trade`     | 0.25% – 5%       | fraction of equity risked per trade                     |
| `max_daily_loss`     | 0.5% – 10%       | day's realized loss that halts new entries              |
| `max_open_positions` | 1 – 20           | concurrent position cap                                 |
| `rr_target`          | 1.0 – 10.0       | take-profit multiple of stop distance                   |
| `timeframe`          | 1Min … 1Day      | bar size used for indicators                            |
| `execution_mode`     | manual / auto    | manual = Telegram approval; auto = no confirmation      |
| `watchlist`          | comma-separated  | symbols to scan                                         |

Credentials (Alpaca keys, Telegram token, chat id) stay in `.env` — they
are not editable from the UI on purpose.

## Project layout

```
bot/
  config.py          env loading (credentials + defaults)
  settings.py        mutable runtime settings (persisted JSON)
  strategy.py        indicators + signal logic
  risk.py            position sizing + daily circuit breaker
  broker.py          Alpaca adapter (data + orders)
  telegram_iface.py  Telegram bot, signal cards w/ approve/reject
  runner.py          async scan loop + signal history
  web.py             FastAPI dashboard (status, settings, logs, tutorial)
web/
  index.html         dashboard markup
  style.css          dark theme
  app.js             vanilla JS, polls API, renders tabs
run.py               entrypoint (uvicorn → FastAPI → bot lifespan)
SETUP.md             full setup tutorial (also rendered in-app)
.env.example
requirements.txt
```
