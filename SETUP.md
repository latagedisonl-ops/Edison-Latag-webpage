# Setup tutorial — from zero to running bot

This walks you from no accounts to a paper-trading bot that pings your
Telegram. **Stay on paper until you're confident.**

---

## 1. Create the accounts

### 1a. Alpaca (broker for stocks/ETFs)

Alpaca is free, has a paper-trading sandbox with $100k of fake money,
and gives you commission-free stock trading via API.

1. Go to <https://alpaca.markets> → **Sign up**.
2. Verify your email. You don't need to fund or do KYC for paper trading.
3. After login, in the top-left switch to **"Paper Trading"**.
4. Left sidebar → **Home** (or Overview). Find the **API Keys** panel
   on the right. Click **Generate New Key**.
5. Copy both values now — the **secret** is shown only once:
   - `APCA-API-KEY-ID` → goes into `ALPACA_API_KEY`
   - `APCA-API-SECRET-KEY` → goes into `ALPACA_API_SECRET`
6. Paper base URL is `https://paper-api.alpaca.markets` (already the default).

> Going live later: regenerate keys from the **Live Trading** dashboard,
> swap base URL to `https://api.alpaca.markets`, and you must complete
> KYC + fund the account.

### 1b. Telegram bot

1. In Telegram, search for **@BotFather** and start a chat.
2. Send `/newbot`. Pick a display name and a unique username ending in
   `bot` (e.g. `mytrader_xyz_bot`).
3. BotFather replies with an **HTTP API token** like
   `7891234567:AAH...`. That's your `TELEGRAM_BOT_TOKEN`.
4. Get **your** chat id: in Telegram search **@userinfobot**, start it,
   it replies with your numeric `Id`. That's your `TELEGRAM_CHAT_ID`.
5. Open a chat with your new bot and press **Start** once — otherwise
   the bot can't message you first.

---

## 2. Install

Requires Python **3.11+**.

```bash
git clone <this-repo-url>
cd Edison-Latag-webpage
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
ALPACA_API_KEY=PK...
ALPACA_API_SECRET=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

TELEGRAM_BOT_TOKEN=7891234567:AAH...
TELEGRAM_CHAT_ID=123456789

WATCHLIST=AAPL,MSFT,NVDA,SPY,QQQ
TIMEFRAME=15Min
RISK_PER_TRADE=0.01          # 1% of equity per trade
MAX_OPEN_POSITIONS=5
MAX_DAILY_LOSS=0.03          # halt if -3% on the day
EXECUTION_MODE=manual        # manual = Telegram approval, auto = no prompt

WEB_HOST=127.0.0.1
WEB_PORT=8787
WEB_AUTH_TOKEN=              # leave empty for localhost-only access
```

> Anything in this file is just a default. Once the bot is running you can
> change `RISK_PER_TRADE`, `WATCHLIST`, `EXECUTION_MODE`, R:R target, and
> max daily loss live from the **Settings** tab in the dashboard. Saved
> values are persisted to `settings.json` and override the env defaults.

---

## 4. Run

```bash
python run.py
```

Expected:

- Console: `Dashboard: http://127.0.0.1:8787` and `Bot started. Mode=manual Paper=True ...`
- Telegram: same message arrives in your chat.
- Open <http://127.0.0.1:8787> in a browser. If `WEB_AUTH_TOKEN` is empty
  and you're on localhost, just press OK on the token prompt. Otherwise
  paste the token.

The dashboard has four tabs:

- **Dashboard** — live equity, day P&L, open positions, recent signals.
- **Settings** — sliders/inputs for risk per trade (default 1%), max
  daily loss, max open positions, R:R target, timeframe, execution mode,
  and watchlist. Hit **Save settings** to apply immediately.
- **Tutorial** — this document, rendered.
- **Logs** — last 300 lines of `bot.log`.

Top-right buttons: **Halt** (stop new entries), **Resume**, **Close All**
(emergency flatten).

Now send `/status` in Telegram — you should get equity + position info.

When the market is open and a signal fires, you'll receive a card:

```
📡 SIGNAL: NVDA LONG
Entry: 132.45  Stop: 130.20  TP: 136.95
R:R = 2.00
Qty: 75 (~$9,933)
Reason: Uptrend + MACD cross + RSI=58.4
[ ✅ Approve ]   [ ❌ Reject ]
```

Tap **Approve** and the bracket order (entry + stop + take-profit) is
sent to Alpaca. Tap **Reject** and nothing happens.

---

## 4a. Picking a strategy

Two are bundled. Switch from the **Settings** tab.

### Confluence (default)

Classic trend-following. Enters when EMA(20)/EMA(50) trend, a MACD cross,
and RSI all line up. Plays best on liquid trending names.

### SMC / ICT

Smart Money Concepts. Tries to enter the way price-action traders do:
*after* a stop hunt and *into* a fresh imbalance, in the direction of a
new structural break.

A long needs:
1. **Bullish BOS** — most recent confirmed swing high taken out by close.
2. **Liquidity sweep** — a recent bar wicks below a prior swing low and
   closes back above it.
3. **Bullish FVG** — an unfilled 3-bar imbalance below current price.

Short setup is the mirror. Stop sits beyond the sweep wick + 0.25×ATR.
Take-profit targets the next opposing swing (untouched liquidity); if
that's too close to give 1.5R, it falls back to `rr_target × risk`.

Heads up: SMC needs structure + sweep + unfilled gap to all exist on the
same scan. On clean trending days you'll see signals; on chop you'll see
none. That's the design — it's quality-over-quantity. It still loses
trades, and it does **not** print money. Backtest before going live.

---

## 5. Going from paper to live (do NOT skip)

Before you flip a single dollar of real money:

1. **Run paper for ≥ 1 month.** Track every trade.
2. **Backtest.** Pull historical bars and replay `strategy.evaluate`
   over them. Compute win-rate, average R, max drawdown. If expectancy
   is negative on history, it'll be negative live.
3. **Tune the watchlist.** This strategy works best on liquid,
   trending names — mega-cap tech and broad ETFs. It chops on
   range-bound penny stocks.
4. **Read Alpaca's PDT rules** if your account is under $25k —
   you're capped at 3 day-trades per rolling 5 sessions.
5. When ready: regenerate **live** keys from Alpaca, change
   `ALPACA_BASE_URL` to `https://api.alpaca.markets`, **start with the
   smallest possible `RISK_PER_TRADE` (e.g. 0.0025 = 0.25%)**, keep
   `EXECUTION_MODE=manual`. Watch every fill.

---

## 6. Operating commands (in Telegram)

- `/status` — equity, day P&L, open positions
- `/halt` — stop new entries (existing positions keep their bracket)
- `/resume` — resume scanning
- `/closeall` — emergency flatten everything

---

## 7. Troubleshooting

- **`Missing required env var`** — fill in `.env` properly, no quotes.
- **Telegram silent** — did you press Start in the bot's chat? Is
  `TELEGRAM_CHAT_ID` numeric and yours?
- **No signals firing** — that's normal. Confluence-based entries are
  rare; you might get 0–3 setups across the watchlist on a quiet day.
- **`market is closed`** — the bot only scans during US regular hours.
- **Order rejected for buying power** — lower `RISK_PER_TRADE`, or
  reduce watchlist.

---

## 8. What this bot is NOT

- Not a guaranteed money printer. Expect losing trades.
- Not high-frequency — 15-minute bars by design.
- Not a replacement for understanding markets. Read *Trading in the
  Zone* (Mark Douglas) and *Technical Analysis of the Financial
  Markets* (John Murphy) before risking real capital.
