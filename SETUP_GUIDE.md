# CRT Forex Alert Bot — Setup Guide

## Folder Structure
```
crt_bot/
├── main.py             ← entry point + scheduler
├── config.py           ← all settings (API keys, pairs, etc.)
├── fetcher.py          ← Twelve Data API
├── indicators.py       ← EMA, ATR, H2 builder
├── detector.py         ← CRT detection logic
├── telegram.py         ← message formatter + sender
├── duplicate_store.py  ← prevent duplicate alerts
├── logger.py           ← console + file logging
├── requirements.txt    ← dependencies
├── crt_bot.log         ← auto-created when bot runs
└── duplicate_store.json← auto-created when bot runs
```

---

## Step 1 — Python Install

**Windows:**
1. https://python.org/downloads → Python 3.11+ download karo
2. Install karte waqt ✅ "Add Python to PATH" check karo
3. Verify: `python --version`

**Linux/VPS:**
```bash
sudo apt update
sudo apt install python3 python3-pip -y
python3 --version
```

---

## Step 2 — Libraries Install

`crt_bot` folder mein jaake run karo:

```bash
pip install -r requirements.txt
```

Verify:
```bash
pip show apscheduler requests
```

---

## Step 3 — Config Setup

`config.py` mein apni values fill karo (already filled hain tumhare liye):

```python
TWELVE_DATA_API_KEY = "your_key_here"
TELEGRAM_BOT_TOKEN  = "your_bot_token"
TELEGRAM_CHAT_ID    = "your_chat_id"
```

---

## Step 4 — Telegram Test

```bash
python main.py --test-telegram
```

Telegram pe message aana chahiye ✅

---

## Step 5 — Manual Test Run

```bash
python main.py --run-now
```

Logs mein dekhna:
- `H1 fetched: 20 candles` ✅
- `H4 fetched: 205 candles` ✅
- `Candle close boundary confirmed` ya `Skipping` ✅

---

## Step 6 — Live Run (Bot Start)

```bash
python main.py
```

Output:
```
[2026-04-30 14:35:00] INFO  — CRT Forex Alert Bot v1.0 — Starting
[2026-04-30 14:35:00] INFO  — Schedule : Every hour at :35 (exact)
[2026-04-30 14:35:00] INFO  — ✅ Scheduler started — next run at :35 UTC
```

Bot hamesha `:35` pe exact run karega. ✅

---

## Step 7 — 24/7 Run (VPS Recommended)

### Option A — Linux VPS (Best)

**Background mein chalao:**
```bash
nohup python3 main.py > /dev/null 2>&1 &
```

**Ya screen use karo (recommended):**
```bash
sudo apt install screen -y
screen -S crtbot
python3 main.py
# Ctrl+A then D to detach
# screen -r crtbot to reattach
```

**Ya systemd service banao (best for VPS):**
```bash
sudo nano /etc/systemd/system/crtbot.service
```
```ini
[Unit]
Description=CRT Forex Alert Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/crt_bot
ExecStart=/usr/bin/python3 /root/crt_bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable crtbot
sudo systemctl start crtbot
sudo systemctl status crtbot
```

### Option B — Windows (Local PC)

Task Scheduler se startup pe run kara sakte ho:
1. Task Scheduler → Create Basic Task
2. Trigger: "At startup"
3. Action: `python C:\path\to\crt_bot\main.py`

---

## Useful Commands

```bash
# Logs real-time dekhna
tail -f crt_bot.log

# Duplicate store reset (test ke baad)
python main.py --reset-store

# Manual ek baar run
python main.py --run-now

# Telegram test
python main.py --test-telegram
```

---

## Timing — How It Works

```
Candle close (IST) : 14:30
Bot trigger (UTC)  : 09:05 UTC = 14:35 IST
Delay              : ~5 minutes ✅

H1, H2, H4 teeno candles IST :30 pe close hote hain
Bot :35 IST pe chalega → 5 min delay hamesha
```

---

## Why Python > Google Apps Script

| Feature | GAS | Python |
|---|---|---|
| Schedule exact time | ❌ ±15 min | ✅ Exact :35 |
| Retry on API fail | ❌ | ✅ 3 retries |
| Log file | ❌ | ✅ |
| VPS 24/7 | ❌ (Google servers) | ✅ |
| Debugging | Hard | Easy |
