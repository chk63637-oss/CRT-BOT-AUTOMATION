import time
import requests
from typing import List, Dict, Optional
from logger import get_logger
from config import TWELVE_DATA_API_KEY, API_SLEEP

log = get_logger("fetcher")


def fetch_candles(pair: str, interval: str, count: int) -> Optional[List[Dict]]:
    """
    Fetch OHLC candles from Twelve Data API.
    Returns list of candles ordered oldest → newest.
    Returns None on failure (after retries).

    interval: "1h" | "4h"
    """
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     pair,
        "interval":   interval,
        "outputsize": count,
        "apikey":     TWELVE_DATA_API_KEY,
        "format":     "JSON",
        "timezone":   "UTC",
    }

    for attempt in range(1, 4):  # 3 retries
        try:
            log.debug(f"Fetching {pair} [{interval}] — attempt {attempt}")
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "error" or "code" in data:
                msg = data.get("message", str(data))
                log.error(f"API error {pair} [{interval}]: {msg}")
                return None

            values = data.get("values", [])
            if len(values) < 2:
                log.error(f"Insufficient candles {pair} [{interval}]: {len(values)}")
                return None

            # Twelve Data returns newest-first → reverse to oldest-first
            candles = []
            for v in reversed(values):
                candles.append({
                    "time":  v["datetime"],
                    "open":  float(v["open"]),
                    "high":  float(v["high"]),
                    "low":   float(v["low"]),
                    "close": float(v["close"]),
                })

            log.debug(f"{pair} [{interval}] fetched {len(candles)} candles")
            return candles

        except requests.RequestException as e:
            log.warning(f"Request failed {pair} [{interval}] attempt {attempt}: {e}")
            if attempt < 3:
                time.sleep(5)

    log.error(f"All retries failed — {pair} [{interval}]")
    return None
