"""
Duplicate alert prevention.
Stores last sent candle time per pair+TF in a local JSON file.
Replaces Google Apps Script's PropertiesService.
"""
import json
import os
from logger import get_logger

log        = get_logger("duplicate_store")
STORE_FILE = "duplicate_store.json"


def _load() -> dict:
    if not os.path.exists(STORE_FILE):
        return {}
    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(store: dict) -> None:
    with open(STORE_FILE, "w") as f:
        json.dump(store, f, indent=2)


def _key(pair: str, tf: str) -> str:
    return f"CRT_LAST_{pair.replace('/', '')}_{tf}"


def is_duplicate(pair: str, tf: str, candle_time: str) -> bool:
    store = _load()
    return store.get(_key(pair, tf)) == candle_time


def mark_sent(pair: str, tf: str, candle_time: str) -> None:
    store = _load()
    store[_key(pair, tf)] = candle_time
    _save(store)


def reset_all(pairs: list, timeframes: list) -> None:
    store = _load()
    for pair in pairs:
        for tf in timeframes:
            k = _key(pair, tf)
            if k in store:
                del store[k]
    _save(store)
    log.info("Duplicate store cleared for all pairs × timeframes.")
