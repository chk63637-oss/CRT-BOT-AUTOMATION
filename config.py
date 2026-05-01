# ╔══════════════════════════════════════════════════════════════╗
#  CRT FOREX ALERT SYSTEM — Python Bot
#  Strategy : Candle Range Theory
#  Version  : 1.0
# ╚══════════════════════════════════════════════════════════════╝

# ── Twelve Data API ───────────────────────────────────────────
TWELVE_DATA_API_KEY = "2a95f1a59c2f458e98518e98f565c67e"

# ── Telegram ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8600766574:AAGiMCzxW6gcPqbKD_iAOJIYnQdhUnFQdB0"
TELEGRAM_CHAT_ID   = "6924587108"

# ── Candle fetch counts ───────────────────────────────────────
H1_CANDLES = 20
H4_CANDLES = 205

# ── CRT filter thresholds ─────────────────────────────────────
MIN_WICK_BODY_RATIO = 2.0
MIN_SWEEP_PIPS = {
    "DEFAULT": 2,
    "JPY":     20,
}
MIN_RANGE_ATR_RATIO = 0.20
EMA_PERIOD          = 200

# ── Kill Zone (UTC hours) ─────────────────────────────────────
# London open → NY close = 07:00–21:00 UTC
KILL_ZONE_START = 7
KILL_ZONE_END   = 21

# ── Pairs to monitor ─────────────────────────────────────────
PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "AUD/USD",
    "NZD/USD",
    "USD/CAD",
    "USD/CHF",
    "GBP/EUR",
    "EUR/CAD",
    "CAD/AUD",
    "NZD/AUD",
    "GBP/NZD",
    "EUR/AUD",
]

# ── API rate limit sleep (seconds) ───────────────────────────
# Twelve Data free = 8 req/min → 8s between calls
API_SLEEP = 10

# ── Scheduler ────────────────────────────────────────────────
# Run at :35 of every hour (IST :35 = candle close + 5 min)
SCHEDULE_MINUTE = 35

# ── Logging ──────────────────────────────────────────────────
LOG_FILE = "crt_bot.log"
