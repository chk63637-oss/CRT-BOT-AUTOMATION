"""
CRT Forex Alert System — Python Bot
Entry point. Runs CRT detection every hour at :35.
"""
import time
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from fetcher        import fetch_candles
from indicators     import compute_ema, build_h2_candles, get_trend_bias, build_trend_note
from detector       import detect_crt, is_tf_candle_closed, build_confluence_note
from telegram       import send_telegram, format_message, send_test_message
from duplicate_store import is_duplicate, mark_sent
from logger         import get_logger

log = get_logger("main")

TIMEFRAMES = ["H1", "H2", "H4"]


# ══════════════════════════════════════════════════════════════
#  KILL ZONE CHECK
# ══════════════════════════════════════════════════════════════
def is_in_kill_zone() -> bool:
    h = datetime.now(timezone.utc).hour
    return config.KILL_ZONE_START <= h < config.KILL_ZONE_END


def get_kill_zone_label() -> str:
    return "London–NY Full Session (07–21 UTC)"


# ══════════════════════════════════════════════════════════════
#  MAIN RUN — called every hour at :35
# ══════════════════════════════════════════════════════════════
def run_crt_alerts() -> None:
    now = datetime.now(timezone.utc)
    log.info(f"=== CRT v1.0 Alert Run — {now.isoformat()} ===")

    # ── Weekend gate ──────────────────────────────────────────
    if now.weekday() >= 5: # 5 = Saturday, 6 = Sunday
        log.info("⏸  Market is closed on weekends. Skipping — no API calls made.")
        return

    # ── Kill zone gate ────────────────────────────────────────
    if not is_in_kill_zone():
        log.info(
            f"⏸  UTC hour {now.hour} outside session "
            f"({config.KILL_ZONE_START}–{config.KILL_ZONE_END} UTC). "
            f"Skipping — no API calls made."
        )
        return

    kill_zone_label = get_kill_zone_label()
    log.info(f"🎯 Active Kill Zone: {kill_zone_label}")

    total_fired = 0

    for pair in config.PAIRS:
        try:
            log.info(f"── Processing {pair} ──────────────────────────")

            # ── 1. Fetch H1 ──────────────────────────────────
            h1 = fetch_candles(pair, "1h", config.H1_CANDLES)
            if not h1:
                log.error(f"H1 fetch failed — {pair}, skipping")
                continue
            log.info(f"  H1 fetched: {len(h1)} candles")
            time.sleep(config.API_SLEEP)

            # ── 2. Fetch H4 ──────────────────────────────────
            h4 = fetch_candles(pair, "4h", config.H4_CANDLES)
            if not h4:
                log.error(f"H4 fetch failed — {pair}, skipping")
                continue
            log.info(f"  H4 fetched: {len(h4)} candles")
            time.sleep(config.API_SLEEP)

            # ── 3. Build H2 ───────────────────────────────────
            h2 = build_h2_candles(h1)
            log.info(f"  H2 built:   {len(h2)} candles")

            # ── 4. EMA200 + trend bias ────────────────────────
            ema200     = compute_ema(h4, config.EMA_PERIOD)
            trend_note = build_trend_note(h4, ema200)
            trend_bias = get_trend_bias(h4, ema200)
            log.info(f"  {trend_note}  [Bias: {trend_bias}]")

            # ── 5. CRT detection across all TFs ──────────────
            tf_sets = [
                {"label": "H1", "candles": h1},
                {"label": "H2", "candles": h2},
                {"label": "H4", "candles": h4},
            ]
            raw_signals = {}

            for tf in tf_sets:
                label   = tf["label"]
                candles = tf["candles"]

                if not candles or len(candles) < 2:
                    log.info(f"  [{label}] insufficient candles — skip")
                    raw_signals[label] = None
                    continue

                # Candle close boundary guard
                if not is_tf_candle_closed(label, candles):
                    log.info(
                        f"  [{label}] ⏩ Skipping — candle NOT at close boundary"
                        f" (UTC hour: {now.hour}). Forming candle risk avoided."
                    )
                    raw_signals[label] = None
                    continue

                log.info(f"  [{label}] ✅ Candle close boundary confirmed — detecting")
                signal = detect_crt(pair, label, candles)

                if not signal:
                    log.info(f"  [{label}] — no valid CRT signal")
                    raw_signals[label] = None
                    continue

                # Suppress WEAK signals
                if signal["strength"] == "★☆☆ WEAK":
                    log.info(f"  [{label}] WEAK signal suppressed")
                    raw_signals[label] = None
                    continue

                # EMA trend filter
                if trend_bias == "NONE":
                    log.info(f"  [{label}] EMA200 unavailable — signal discarded")
                    raw_signals[label] = None
                    continue

                if signal["direction"] != trend_bias:
                    log.info(
                        f"  [{label}] ❌ Trend filter blocked — "
                        f"{signal['direction']} discarded (H4 bias is {trend_bias})"
                    )
                    raw_signals[label] = None
                    continue

                # Signal passed all filters
                raw_signals[label] = signal
                log.info(
                    f"  [{label}] ✅ {signal['direction']}"
                    f" | {signal['strength']}"
                    f" | sweep {signal['sweep_pips']} pips"
                    f" | wick/body {signal['wick_body_ratio']}×"
                    f" | trend ✓ ({trend_bias})"
                )

            # ── 6. Confluence note ────────────────────────────
            confluence_note = build_confluence_note(raw_signals)
            if confluence_note:
                log.info(f"  {confluence_note}")

            # ── 7. Fire alerts ────────────────────────────────
            for tf_label, signal in raw_signals.items():
                if not signal:
                    continue

                if is_duplicate(pair, tf_label, signal["candle_time"]):
                    log.info(f"  ⏭  Duplicate — {pair} [{tf_label}]")
                    continue

                msg = format_message(
                    pair, tf_label, signal,
                    trend_note, confluence_note, kill_zone_label
                )
                if send_telegram(msg):
                    mark_sent(pair, tf_label, signal["candle_time"])
                    log.info(f"  📲 Alert sent — {pair} [{tf_label}] {signal['direction']}")
                    total_fired += 1
                else:
                    log.error(f"  ❌ Telegram send failed — {pair} [{tf_label}]")

        except Exception as e:
            log.error(f"❌ Error — {pair}: {e}", exc_info=True)

    log.info(f"=== Run complete. Total alerts sent: {total_fired} ===")


# ══════════════════════════════════════════════════════════════
#  SCHEDULER SETUP — exact :35 every hour
# ══════════════════════════════════════════════════════════════
def main():
    # Handle command-line args
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--test-telegram":
            send_test_message()
            return
        if arg == "--run-now":
            run_crt_alerts()
            return
        if arg == "--reset-store":
            from duplicate_store import reset_all
            reset_all(config.PAIRS, TIMEFRAMES)
            return

    log.info("╔══════════════════════════════════════════╗")
    log.info("║   CRT Forex Alert Bot v1.0 — Starting    ║")
    log.info("╚══════════════════════════════════════════╝")
    log.info(f"Pairs    : {len(config.PAIRS)}")
    log.info(f"Schedule : Every hour at :{config.SCHEDULE_MINUTE:02d} (exact)")
    log.info(f"Session  : {config.KILL_ZONE_START}:00–{config.KILL_ZONE_END}:00 UTC")

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    # Fire at exactly :35 of every hour
    scheduler.add_job(
        run_crt_alerts,
        trigger="cron",
        minute=config.SCHEDULE_MINUTE,
        id="crt_alerts",
        max_instances=1,
        misfire_grace_time=120,  # allow 2 min late if server was busy
    )

    log.info(f"✅ Scheduler started — next run at :{config.SCHEDULE_MINUTE:02d} IST")
    log.info("   Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped by user.")


if __name__ == "__main__":
    main()
