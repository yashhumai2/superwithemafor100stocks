"""Scanner configuration — mirrors your TradingView Dual Supertrend settings."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Timeframe (strict) ---
TIMEFRAME = "4h"
LOOKBACK_DAYS = 120  # enough for EMA 200 on 4H

# --- 5 EMAs (change here if your chart uses different lengths) ---
EMA_PERIODS = [int(x) for x in os.getenv("EMA_PERIODS", "9,21,50,100,200").split(",")]

# --- Dual Supertrend (from your Pine script) ---
ST1_ATR_LENGTH = 13
ST1_FACTOR = 2.0
ST2_ATR_LENGTH = 13
ST2_FACTOR = 4.0

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Scan behaviour ---
# Only alert on bars that just flipped (same as buySignal/sellSignal in Pine)
# Set True to also list stocks currently above/below all EMAs even without a fresh ST flip
INCLUDE_EMA_ONLY_SNAPSHOT = False

# Dedup: don't re-send same symbol+side within this many hours
ALERT_COOLDOWN_HOURS = 8

# Min hours between full scans (UptimeRobot free pings ~every 5 min)
SCAN_INTERVAL_HOURS = float(os.getenv("SCAN_INTERVAL_HOURS", "4"))