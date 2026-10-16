"""Send alert messages to Telegram."""

from __future__ import annotations

import requests


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        print("[telegram] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — printing only:")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[telegram] send failed: {e}")
        return False


def format_scan_message(
    buys: list[dict],
    sells: list[dict],
    timeframe: str,
    ema_periods: list[int],
) -> str:
    lines = [
        f"<b>NSE Top 100 — {timeframe.upper()} Scan</b>",
        f"Today only: fresh Dual Supertrend arrow + EMA filter {ema_periods}",
        "",
    ]

    if buys:
        lines.append("<b>🟢 BUY</b> (ST just flipped green + above all 5 EMAs)")
        for s in buys:
            lines.append(
                f"• <b>{s['symbol']}</b>  ₹{s['close']:.2f}  "
                f"<i>{s['time']}</i>"
            )
        lines.append("")
    else:
        lines.append("🟢 BUY: none")
        lines.append("")

    if sells:
        lines.append("<b>🔴 SELL</b> (ST just flipped red + below all 5 EMAs)")
        for s in sells:
            lines.append(
                f"• <b>{s['symbol']}</b>  ₹{s['close']:.2f}  "
                f"<i>{s['time']}</i>"
            )
        lines.append("")
    else:
        lines.append("🔴 SELL: none")
        lines.append("")

    if not buys and not sells:
        lines.append("<i>No fresh signals on the latest closed 4H bar.</i>")

    return "\n".join(lines)
