# NSE Top 100 — Dual Supertrend + 5 EMA Telegram Alerts

Scans **Nifty 100** stocks on the **4H** timeframe and sends Telegram updates when:

| Side | Condition |
|------|-----------|
| **BUY** (green) | Both Supertrends just flipped green **and** close is **above all 5 EMAs** |
| **SELL** (red ▼) | Both Supertrends just flipped red **and** close is **below all 5 EMAs** |

Pivots from the TradingView script are **ignored**. Only Dual Supertrend + EMAs are used.

## Matches your Pine script

- Supertrend 1: ATR length **13**, factor **2.0**
- Supertrend 2: ATR length **13**, factor **4.0**
- Flip logic: both green / both red vs previous bar (same as `buySignal` / `sellSignal`)

Default EMAs: **9, 21, 50, 100, 200** — change in `config.py` or `.env` if your chart uses different lengths.

## Setup

```powershell
cd c:\Users\admin\Desktop\superwithemafor100stocks
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Create a bot with [@BotFather](https://t.me/BotFather), then get your chat id from [@userinfobot](https://t.me/userinfobot).

## Run once

```powershell
# Full scan + Telegram
python scanner.py

# Print only (no Telegram)
python scanner.py --dry-run

# Debug one stock
python scanner.py --symbol RELIANCE
```

## Schedule (Windows Task Scheduler)

Run after each 4H close during NSE hours (approx **09:15, 13:15 IST** — adjust if your broker’s 4H session differs):

```
Program:  c:\Users\admin\Desktop\superwithemafor100stocks\.venv\Scripts\python.exe
Arguments: scanner.py
Start in:  c:\Users\admin\Desktop\superwithemafor100stocks
```

Or loop every 30 minutes while the market is open:

```powershell
python run_loop.py
```

## Change EMA lengths

In `.env`:

```
EMA_PERIODS=20,50,100,150,200
```

Or edit `EMA_PERIODS` in `config.py`.
