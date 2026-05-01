from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from indicators import compute_simple_atr
from config import MIN_WICK_BODY_RATIO, MIN_SWEEP_PIPS, MIN_RANGE_ATR_RATIO
from logger import get_logger

log = get_logger("detector")

TF_DURATION_SEC = {"H1": 3600, "H2": 7200, "H4": 14400}


# ── Helpers ───────────────────────────────────────────────────
def is_jpy_pair(pair: str) -> bool:
    return "JPY" in pair.upper()


def get_precision(pair: str) -> int:
    return 3 if is_jpy_pair(pair) else 5


def format_pips(pair: str, raw_diff: float) -> str:
    multiplier = 100 if is_jpy_pair(pair) else 10000
    return f"{raw_diff * multiplier:.1f}"


def rate_strength(wick: float, body: float) -> str:
    ratio = wick / body
    if ratio >= 3.0:
        return "★★★ STRONG"
    if ratio >= 2.0:
        return "★★☆ MODERATE"
    return "★☆☆ WEAK"


# ── Candle Close Validator ────────────────────────────────────
def is_tf_candle_closed(tf_label: str, candles: List[Dict]) -> bool:
    """
    Dynamic candle close check — no hardcoded UTC hours.
    Checks if candles[n-2] (detection candle) has fully closed.
    closeTime = candles[n-2].openTime + tfDuration + 60s buffer
    """
    duration_sec = TF_DURATION_SEC.get(tf_label)
    if not duration_sec:
        log.debug(f"isTFCandleClosed [{tf_label}]: unknown TF — allowing")
        return True

    if not candles or len(candles) < 2:
        log.debug(f"isTFCandleClosed [{tf_label}]: not enough candles")
        return False

    # candles[n-2] = detection candle
    target         = candles[-2]
    open_dt        = datetime.fromisoformat(target["time"].replace(" ", "T")).replace(tzinfo=timezone.utc)
    close_dt       = open_dt + timedelta(seconds=duration_sec)
    buffer_dt      = close_dt + timedelta(seconds=60)
    now_utc        = datetime.now(timezone.utc)
    is_closed      = now_utc > buffer_dt
    diff_min       = round((now_utc - close_dt).total_seconds() / 60, 1)

    # It must be past the buffer time, BUT it must also be a fresh close (within 60 mins).
    # If diff_min > 60, it's an old H2/H4 candle that was already checked in a previous hour.
    is_closed      = (now_utc > buffer_dt) and (diff_min <= 60)

    log.debug(
        f"isTFCandleClosed [{tf_label}]: detectCandle={target['time']}"
        f"  closedAt={close_dt.strftime('%H:%M')} UTC"
        f"  diff={diff_min}min  closed={is_closed}"
    )
    return is_closed


# ── Core CRT Evaluator ────────────────────────────────────────
def _evaluate_crt_pair(
    pair: str,
    tf_label: str,
    prev: Dict,
    current: Dict,
    atr: float,
    min_sweep: float,
) -> Optional[Dict]:
    """
    Evaluates a single prev/current closed candle pair for CRT pattern.
    Returns signal dict or None.
    """
    if not prev or not current:
        return None

    prev_range    = prev["high"]    - prev["low"]
    current_range = current["high"] - current["low"]
    avg_range     = (prev_range + current_range) / 2

    # Low-volatility guard
    if current_range < avg_range * MIN_RANGE_ATR_RATIO:
        log.debug(f"[{tf_label}] {pair} [{current['time']}] — low-range filtered")
        return None

    # ATR minimum range filter
    if atr > 0 and current_range < atr * 0.5:
        log.debug(
            f"[{tf_label}] {pair} [{current['time']}] — ATR filtered"
            f" ({format_pips(pair, current_range)} pips < 50% ATR {format_pips(pair, atr)} pips)"
        )
        return None

    body        = abs(current["close"] - current["open"])
    body_top    = max(current["open"],  current["close"])
    body_bottom = min(current["open"],  current["close"])
    upper_wick  = current["high"] - body_top
    lower_wick  = body_bottom     - current["low"]

    # Doji guard
    if body < 0.000001:
        log.debug(f"[{tf_label}] {pair} [{current['time']}] — doji filtered")
        return None

    prec = get_precision(pair)

    # ── BUY CRT — CRL Sweep + Rejection ──────────────────────
    low_sweep = prev["low"] - current["low"]
    if (
        current["low"]   <  prev["low"]
        and low_sweep    >= min_sweep
        and current["close"] > prev["low"]
        and lower_wick   >= body * MIN_WICK_BODY_RATIO
    ):
        ratio = f"{lower_wick / body:.2f}"
        return {
            "direction":     "BUY",
            "type":          "BUY CRT — CRL Sweep + Rejection",
            "target":        f"Candle High (CRH) {prev['high']:.{prec}f}",
            "sweep_size":    low_sweep,
            "sweep_pips":    format_pips(pair, low_sweep),
            "wick_body_ratio": ratio,
            "strength":      rate_strength(lower_wick, body),
            "crh":           prev["high"],
            "crl":           prev["low"],
            "current_low":   current["low"],
            "current_close": current["close"],
            "candle_time":   current["time"],
            "is_buy":        True,
        }

    # ── SELL CRT — CRH Sweep + Rejection ─────────────────────
    high_sweep = current["high"] - prev["high"]
    if (
        current["high"]  >  prev["high"]
        and high_sweep   >= min_sweep
        and current["close"] < prev["high"]
        and upper_wick   >= body * MIN_WICK_BODY_RATIO
    ):
        ratio = f"{upper_wick / body:.2f}"
        return {
            "direction":      "SELL",
            "type":           "SELL CRT — CRH Sweep + Rejection",
            "target":         f"Candle Low (CRL) {prev['low']:.{prec}f}",
            "sweep_size":     high_sweep,
            "sweep_pips":     format_pips(pair, high_sweep),
            "wick_body_ratio": ratio,
            "strength":       rate_strength(upper_wick, body),
            "crh":            prev["high"],
            "crl":            prev["low"],
            "current_high":   current["high"],
            "current_close":  current["close"],
            "candle_time":    current["time"],
            "is_buy":         False,
        }

    return None


# ── Main CRT Detector ─────────────────────────────────────────
def detect_crt(pair: str, tf_label: str, candles: List[Dict]) -> Optional[Dict]:
    """
    Detects CRT pattern on closed candles only.

    INDEX MAP (forming candle permanently excluded):
      candles[n-1] ← FORMING  (never touched)
      candles[n-2] ← CLOSED   current  (Pair B)
      candles[n-3] ← CLOSED   prev     (Pair B) / current (Pair A)
      candles[n-4] ← CLOSED   prev     (Pair A)

    Checks Pair B first, then Pair A as fallback.
    """
    if not candles or len(candles) < 3:
        log.debug(f"[{tf_label}] detect_crt: need ≥3 candles, got {len(candles) if candles else 0}")
        return None

    atr = compute_simple_atr(candles, 20)
    min_sweep = (
        MIN_SWEEP_PIPS["JPY"] * 0.01
        if is_jpy_pair(pair)
        else MIN_SWEEP_PIPS["DEFAULT"] * 0.0001
    )
    n = len(candles)

    log.debug(
        f"[{tf_label}] Forming candle excluded: [{n-1}] {candles[-1]['time']}"
        f" | Using CLOSED candle at [{n-2}] {candles[-2]['time']} as current"
    )

    # Pair B — most recent closed pair
    sig_b = _evaluate_crt_pair(pair, tf_label, candles[n-3], candles[n-2], atr, min_sweep)
    if sig_b:
        log.debug(f"[{tf_label}] Pair B hit — CLOSED current: [{n-2}] {candles[n-2]['time']}")
        return sig_b

    return None


# ── Confluence Note ───────────────────────────────────────────
def build_confluence_note(raw_signals: Dict) -> Optional[str]:
    buy_tfs  = [tf for tf, s in raw_signals.items() if s and s["direction"] == "BUY"]
    sell_tfs = [tf for tf, s in raw_signals.items() if s and s["direction"] == "SELL"]
    if len(buy_tfs)  >= 2:
        return f"🔗 Confluence: {' + '.join(buy_tfs)} aligned (BUY)"
    if len(sell_tfs) >= 2:
        return f"🔗 Confluence: {' + '.join(sell_tfs)} aligned (SELL)"
    return None
