"""Poll the scanner every N minutes during market hours (IST)."""

from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta, timezone

from scanner import run_scan

IST = timezone(timedelta(hours=5, minutes=30))
POLL_MINUTES = 30
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 35)


def market_open_now() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


if __name__ == "__main__":
    print(f"Loop every {POLL_MINUTES}m during NSE hours (IST). Ctrl+C to stop.")
    while True:
        if market_open_now():
            try:
                run_scan(send=True)
            except Exception as e:
                print(f"Scan error: {e}")
        else:
            print(f"[{datetime.now(IST):%Y-%m-%d %H:%M IST}] market closed — sleeping")
        time.sleep(POLL_MINUTES * 60)
