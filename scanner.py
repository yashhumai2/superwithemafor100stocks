"""
NSE Top 100 scanner — 4H Dual Supertrend + 5 EMA filter → Telegram.

Signal rules (pivots ignored):
  BUY  = both Supertrends just flipped green  AND close > all 5 EMAs
  SELL = both Supertrends just flipped red    AND close < all 5 EMAs

Supertrend params match your Pine script: ATR 13 / factor 2.0 and ATR 13 / factor 4.0
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

import config
from indicators import add_indicators
from nse_top100 import NIFTY_100, yf_symbol
from telegram_notify import format_scan_message, send_telegram

STATE_FILE = Path(__file__).with_name("alert_state.json")
IST = timezone(timedelta(hours=5, minutes=30))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def cooldown_ok(state: dict, key: str) -> bool:
    last = state.get(key)
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_dt >= timedelta(
        hours=config.ALERT_COOLDOWN_HOURS
    )


def mark_sent(state: dict, key: str) -> None:
    state[key] = datetime.now(timezone.utc).isoformat()


def fetch_4h(symbol: str) -> pd.DataFrame | None:
    ticker = yf_symbol(symbol)
    try:
        df = yf.download(
            ticker,
            period=f"{config.LOOKBACK_DAYS}d",
            interval=config.TIMEFRAME,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception as e:
        print(f"  [{symbol}] download error: {e}")
        return None

    if df is None or df.empty:
        return None

    # yfinance sometimes returns MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    need = {"Open", "High", "Low", "Close"}
    if not need.issubset(set(df.columns)):
        return None

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) < max(config.EMA_PERIODS) + 30:
        return None
    return df


def evaluate_symbol(symbol: str) -> dict | None:
    """Return alert dict if latest closed 4H bar has buy/sell alert."""
    df = fetch_4h(symbol)
    if df is None:
        return None

    ind = add_indicators(
        df,
        config.EMA_PERIODS,
        config.ST1_ATR_LENGTH,
        config.ST1_FACTOR,
        config.ST2_ATR_LENGTH,
        config.ST2_FACTOR,
    )

    # Prefer the previous bar (fully closed); also check last bar for a fresh flip.
    candidates = []
    if len(ind) > 1:
        candidates.append(ind.iloc[-2])
    candidates.append(ind.iloc[-1])

    for row in candidates:
        ts = row.name
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if getattr(ts, "tzinfo", None) is None:
            ts_str = str(ts)
        else:
            ts_str = ts.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")

        base = {
            "symbol": symbol,
            "close": float(row["Close"]),
            "time": ts_str,
            "above_all_emas": bool(row["above_all_emas"]),
            "below_all_emas": bool(row["below_all_emas"]),
        }

        if bool(row["buy_alert"]):
            return {**base, "side": "BUY"}
        if bool(row["sell_alert"]):
            return {**base, "side": "SELL"}

    if config.INCLUDE_EMA_ONLY_SNAPSHOT:
        last = ind.iloc[-1]
        ts = last.name
        ts_str = str(ts)
        if bool(last["above_all_emas"]):
            return {
                "symbol": symbol,
                "close": float(last["Close"]),
                "time": ts_str,
                "side": "ABOVE_EMAS",
                "above_all_emas": True,
                "below_all_emas": False,
            }
        if bool(last["below_all_emas"]):
            return {
                "symbol": symbol,
                "close": float(last["Close"]),
                "time": ts_str,
                "side": "BELOW_EMAS",
                "above_all_emas": False,
                "below_all_emas": True,
            }

    return None


def run_scan(send: bool = True) -> tuple[list[dict], list[dict]]:
    print(
        f"Scanning {len(NIFTY_100)} NSE names on {config.TIMEFRAME} | "
        f"EMAs={config.EMA_PERIODS} | "
        f"ST=({config.ST1_ATR_LENGTH},{config.ST1_FACTOR})+"
        f"({config.ST2_ATR_LENGTH},{config.ST2_FACTOR})"
    )
    buys: list[dict] = []
    sells: list[dict] = []
    state = load_state()

    for i, symbol in enumerate(NIFTY_100, 1):
        print(f"[{i}/{len(NIFTY_100)}] {symbol}...", end=" ", flush=True)
        try:
            hit = evaluate_symbol(symbol)
        except Exception as e:
            print(f"ERR {e}")
            continue

        if hit is None:
            print("—")
            time.sleep(0.15)  # be gentle with Yahoo
            continue

        side = hit["side"]
        key = f"{symbol}:{side}:{hit['time']}"
        if not cooldown_ok(state, key) and side in ("BUY", "SELL"):
            print(f"{side} (cooldown skip)")
            time.sleep(0.15)
            continue

        print(side)
        if side == "BUY":
            buys.append(hit)
            mark_sent(state, key)
        elif side == "SELL":
            sells.append(hit)
            mark_sent(state, key)

        time.sleep(0.15)

    save_state(state)

    msg = format_scan_message(buys, sells, config.TIMEFRAME, config.EMA_PERIODS)
    print("\n" + "=" * 50)
    print(msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    print("=" * 50)

    if send:
        ok = send_telegram(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)
        print("Telegram:", "sent" if ok else "not sent")

    return buys, sells


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NSE Top 100 Dual ST + EMA Telegram scanner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results only; do not call Telegram API",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="",
        help="Test a single NSE symbol (e.g. RELIANCE)",
    )
    args = parser.parse_args()

    if args.symbol:
        sym = args.symbol.upper()
        df = fetch_4h(sym)
        if df is None:
            print(f"No data for {sym}")
        else:
            ind = add_indicators(
                df,
                config.EMA_PERIODS,
                config.ST1_ATR_LENGTH,
                config.ST1_FACTOR,
                config.ST2_ATR_LENGTH,
                config.ST2_FACTOR,
            )
            row = ind.iloc[-1]
            print(f"{sym} last bar: {row.name}")
            print(f"  Close={row['Close']:.2f}")
            for p in config.EMA_PERIODS:
                print(f"  EMA{p}={row[f'ema_{p}']:.2f}")
            print(f"  ST dirs: {int(row['st1_dir'])}, {int(row['st2_dir'])}  "
                  f"(<0 green, >0 red)")
            print(f"  both_green={bool(row['both_green'])} both_red={bool(row['both_red'])}")
            print(f"  above_all_emas={bool(row['above_all_emas'])} "
                  f"below_all_emas={bool(row['below_all_emas'])}")
            print(f"  buy_alert={bool(row['buy_alert'])} sell_alert={bool(row['sell_alert'])}")
            hit = evaluate_symbol(sym)
            print("Alert:", hit or "none on last 2 bars")
    else:
        run_scan(send=not args.dry_run)
