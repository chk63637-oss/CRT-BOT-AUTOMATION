from typing import List, Dict, Optional
from math import floor
from logger import get_logger

log = get_logger("indicators")


# ── EMA ───────────────────────────────────────────────────────
def compute_ema(candles: List[Dict], period: int) -> Optional[float]:
    """
    Standard EMA. Seed = SMA of first `period` bars.
    Returns final EMA value or None if insufficient data.
    """
    if not candles or len(candles) < period:
        log.debug(f"EMA: insufficient data ({len(candles) if candles else 0} bars, need {period})")
        return None

    k   = 2 / (period + 1)
    ema = sum(c["close"] for c in candles[:period]) / period

    for c in candles[period:]:
        ema = c["close"] * k + ema * (1 - k)

    return ema


# ── Robust Median ATR ───────────────────────────────────────
def compute_simple_atr(candles: List[Dict], period: int) -> float:
    """
    Robust ATR using MEDIAN of high-low ranges.
    Median is immune to outlier candles (bad API data, spikes).
    Also filters ranges > 3x median to remove extreme outliers.
    Uses last `period` candles or all available.
    """
    if not candles:
        return 0.0
    subset = candles[-period:]
    ranges = sorted(c["high"] - c["low"] for c in subset)
    if not ranges:
        return 0.0
    # Median
    mid   = len(ranges) // 2
    median = (ranges[mid - 1] + ranges[mid]) / 2 if len(ranges) % 2 == 0 else ranges[mid]
    # Filter outliers > 3x median before returning
    clean = [r for r in ranges if r <= median * 3]
    if not clean:
        return median
    return sum(clean) / len(clean)


# ── H2 Builder ───────────────────────────────────────────────
def _h2_bucket_key(datetime_str: str) -> str:
    """
    Maps H1 candle datetime to its H2 bucket key.
    "2026-04-29 03:00:00" → "2026-04-29 02:00:00"
    """
    date_part, time_part = datetime_str.split(" ")
    hour   = int(time_part.split(":")[0])
    bucket = floor(hour / 2) * 2
    return f"{date_part} {bucket:02d}:00:00"


def build_h2_candles(h1_candles: List[Dict]) -> List[Dict]:
    """
    Builds H2 candles from H1 using UTC time alignment.
    Discards incomplete buckets (not exactly 2 H1 bars).
    """
    if not h1_candles or len(h1_candles) < 4:
        log.debug(f"H2 build: need ≥4 H1 bars, got {len(h1_candles) if h1_candles else 0}")
        return []

    buckets      = {}
    bucket_order = []

    for candle in h1_candles:
        key = _h2_bucket_key(candle["time"])
        if key not in buckets:
            buckets[key] = []
            bucket_order.append(key)
        buckets[key].append(candle)

    h2_candles = []
    for key in bucket_order:
        group = buckets[key]
        if len(group) != 2:
            log.debug(f"H2 bucket {key} — {len(group)} bar(s), discarded")
            continue
        first, last = group[0], group[1]
        h2_candles.append({
            "time":  key,
            "open":  first["open"],
            "close": last["close"],
            "high":  max(first["high"], last["high"]),
            "low":   min(first["low"],  last["low"]),
        })

    return h2_candles


# ── Trend Bias ────────────────────────────────────────────────
def get_trend_bias(h4_candles: List[Dict], ema200: Optional[float]) -> str:
    """
    Returns "BUY" | "SELL" | "NONE" based on H4 EMA200.
    Buffer zone suppresses signals when price hugs EMA.
    """
    if ema200 is None or not h4_candles:
        return "NONE"

    last_close = h4_candles[-1]["close"]
    multiplier = 0.001 if last_close > 50 else 0.0002  # JPY vs others
    buffer     = ema200 * multiplier
    upper      = ema200 + buffer
    lower      = ema200 - buffer

    log.debug(
        f"EMA bias — close:{last_close:.5f}  EMA:{ema200:.5f}"
        f"  upper:{upper:.5f}  lower:{lower:.5f}"
    )

    if last_close > upper:
        return "BUY"
    if last_close < lower:
        return "SELL"

    log.debug("Price inside EMA buffer zone — bias: NONE")
    return "NONE"


def build_trend_note(h4_candles: List[Dict], ema200: Optional[float]) -> str:
    if ema200 is None:
        return "📊 Trend (H4 200 EMA): N/A (insufficient data)"
    last_close  = h4_candles[-1]["close"]
    label       = "🟢 Bullish" if last_close > ema200 else "🔴 Bearish"
    return f"📊 Trend (H4 200 EMA): {label}  _(price: {last_close:.5f} | EMA: {ema200:.5f})_"
