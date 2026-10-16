"""
Render Web Service entrypoint.

- GET /         → health check (keeps deploy green)
- GET /scan     → run NSE 4H scan → Telegram
  Optional: ?key=YOUR_SCAN_SECRET if SCAN_SECRET is set

Use a free external cron (cron-job.org) to hit /scan every 4 hours,
or use Render Cron Job (paid) with startCommand: python scanner.py
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import config
from scanner import run_scan

app = Flask(__name__)

_scan_lock = threading.Lock()
_last_scan: dict = {"at": None, "buys": 0, "sells": 0, "error": None}


def _authorized() -> bool:
    secret = os.getenv("SCAN_SECRET", "").strip()
    if not secret:
        return True
    return request.args.get("key", "") == secret or request.headers.get("X-Scan-Key") == secret


def _do_scan() -> dict:
    with _scan_lock:
        try:
            buys, sells = run_scan(send=True)
            _last_scan.update(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "buys": len(buys),
                    "sells": len(sells),
                    "error": None,
                }
            )
            return {"ok": True, "buys": len(buys), "sells": len(sells)}
        except Exception as e:
            _last_scan["error"] = str(e)
            _last_scan["at"] = datetime.now(timezone.utc).isoformat()
            return {"ok": False, "error": str(e)}


@app.get("/")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "nse-dual-st-ema-scanner",
            "timeframe": config.TIMEFRAME,
            "emas": config.EMA_PERIODS,
            "last_scan": _last_scan,
        }
    )


@app.get("/scan")
@app.post("/scan")
def scan():
    if not _authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if _scan_lock.locked():
        return jsonify({"ok": False, "error": "scan already running"}), 409
    result = _do_scan()
    code = 200 if result.get("ok") else 500
    return jsonify(result), code


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
