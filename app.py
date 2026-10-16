"""
Render Web Service entrypoint.

- GET /         → health check
- GET /scan     → run NSE 4H scan → Telegram (throttled to every SCAN_INTERVAL_HOURS)
  ?key=SCAN_SECRET  (required if SCAN_SECRET is set)
  ?force=1          → bypass 4h throttle (manual test)

UptimeRobot free checks ~every 5 minutes; server only runs a real scan every 4h.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

import config
from scanner import run_scan

app = Flask(__name__)

_scan_lock = threading.Lock()
_last_scan: dict = {"at": None, "buys": 0, "sells": 0, "error": None, "skipped": False}


def _authorized() -> bool:
    secret = os.getenv("SCAN_SECRET", "").strip()
    if not secret:
        return True
    return request.args.get("key", "") == secret or request.headers.get("X-Scan-Key") == secret


def _hours_since_last_scan() -> float | None:
    if not _last_scan.get("at"):
        return None
    try:
        last = datetime.fromisoformat(_last_scan["at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
    except ValueError:
        return None


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
                    "skipped": False,
                }
            )
            return {"ok": True, "buys": len(buys), "sells": len(sells)}
        except Exception as e:
            _last_scan["error"] = str(e)
            _last_scan["at"] = datetime.now(timezone.utc).isoformat()
            _last_scan["skipped"] = False
            return {"ok": False, "error": str(e)}


@app.get("/")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "nse-dual-st-ema-scanner",
            "timeframe": config.TIMEFRAME,
            "emas": config.EMA_PERIODS,
            "scan_interval_hours": config.SCAN_INTERVAL_HOURS,
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

    force = request.args.get("force", "") in ("1", "true", "yes")
    hours = _hours_since_last_scan()
    if (
        not force
        and hours is not None
        and hours < config.SCAN_INTERVAL_HOURS
    ):
        remaining = round(config.SCAN_INTERVAL_HOURS - hours, 2)
        _last_scan["skipped"] = True
        return jsonify(
            {
                "ok": True,
                "skipped": True,
                "reason": f"next scan in ~{remaining}h (UptimeRobot throttle)",
                "last_scan": _last_scan.get("at"),
                "interval_hours": config.SCAN_INTERVAL_HOURS,
            }
        ), 200

    result = _do_scan()
    code = 200 if result.get("ok") else 500
    return jsonify(result), code


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
