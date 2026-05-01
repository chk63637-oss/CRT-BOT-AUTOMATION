import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from logger import get_logger

log = get_logger("telegram")


# ── IST Converter ─────────────────────────────────────────────
def convert_to_ist(utc_str: str) -> str:
    """
    Converts UTC datetime string to IST (UTC+5:30) with AM/PM.
    Input:  "2026-04-29 06:00:00"
    Output: "29 Apr 2026  11:30 AM IST"
    """
    dt_utc = datetime.fromisoformat(utc_str.replace(" ", "T")).replace(tzinfo=timezone.utc)
    dt_ist = dt_utc + timedelta(hours=5, minutes=30)

    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    hour   = dt_ist.hour
    ampm   = "AM" if hour < 12 else "PM"
    h12    = hour % 12 or 12
    return f"{dt_ist.day} {months[dt_ist.month-1]} {dt_ist.year}  {h12}:{dt_ist.minute:02d} {ampm} IST"


# ── Message Formatter ─────────────────────────────────────────
def format_message(
    pair: str,
    tf_label: str,
    signal: dict,
    trend_note: str,
    confluence_note: Optional[str],
    kill_zone_label: str,
) -> str:
    is_buy = signal["direction"] == "BUY"
    emoji  = "🟢" if is_buy else "🔴"
    arrow  = "↗"  if is_buy else "↘"
    prec   = 3 if "JPY" in pair.upper() else 5

    lines = [
        f"{emoji} *{pair}*  {arrow}  \\[{tf_label}\\]",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 *{signal['type']}*",
        f"🕐 *Time (IST):*  `{convert_to_ist(signal['candle_time'])}`",
        f"🎯 *Kill Zone:*   {kill_zone_label}",
        "━━━━━━━━━━━━━━━━━━━━",
        "📐 *Candle Reference Range*",
        f"   CRH: `{signal['crh']:.{prec}f}`",
        f"   CRL: `{signal['crl']:.{prec}f}`",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if is_buy:
        lines.append(f"📉 Sweep Low:  `{signal['current_low']:.{prec}f}` _(breached CRL)_")
        lines.append(f"📈 Close:      `{signal['current_close']:.{prec}f}` _(rejected back above CRL)_")
    else:
        lines.append(f"📈 Sweep High: `{signal['current_high']:.{prec}f}` _(breached CRH)_")
        lines.append(f"📉 Close:      `{signal['current_close']:.{prec}f}` _(rejected back below CRH)_")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"📏 Sweep Size:  *{signal['sweep_pips']} pips*",
        f"📊 Wick/Body:   *{signal['wick_body_ratio']}×*",
        f"💪 Strength:    *{signal['strength']}*",
        f"🎯 Target:      `{signal['target']}`",
        "━━━━━━━━━━━━━━━━━━━━",
        trend_note or "📊 Trend (H4 200 EMA): N/A",
        f"🔒 *Trend Filter: ACTIVE — {signal['direction']} signals only*",
    ]

    if confluence_note:
        lines.append(confluence_note)

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"_CRT Alert System v1.0 — {tf_label} Timeframe_",
    ]

    return "\n".join(lines)


# ── Sender ────────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    """
    Sends message to Telegram. Returns True on success.
    """
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok"):
            log.error(f"Telegram rejected: {result}")
            return False
        return True
    except requests.RequestException as e:
        log.error(f"Telegram send failed: {e}")
        return False


def send_test_message() -> None:
    send_telegram(
        "🔔 *CRT Alert System v1.0 (Python) — Connection Test*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Telegram: Connected\n"
        "🎯 Kill Zone (07–21 UTC): ACTIVE\n"
        "📐 CRT Logic (Sweep + Rejection): ACTIVE\n"
        "📊 Multi-Timeframe (H1 / H2 / H4): ACTIVE\n"
        "📈 H4 200 EMA — Strict Trend Filter: ACTIVE\n"
        "🚫 Forming Candle Excluded: ACTIVE\n"
        "🔒 Dynamic Candle Close Guard: ACTIVE\n"
        "⏰ Exact :35 Scheduling (APScheduler): ACTIVE\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "_All systems operational._"
    )
    log.info("Test message sent to Telegram.")
