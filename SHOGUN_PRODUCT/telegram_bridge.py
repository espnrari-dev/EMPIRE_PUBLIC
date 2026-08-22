#!/usr/bin/env python3
"""SHOGUN Telegram Bridge – real status and control."""
import time, requests, json, subprocess, pathlib
from datetime import datetime, timezone

TOKEN = pathlib.Path.home().joinpath("token.txt").read_text().strip() if pathlib.Path.home().joinpath("token.txt").exists() else ""
if not TOKEN:
    print("No token.txt found. Bridge disabled.")
    exit(1)

URL = f"https://api.telegram.org/bot{TOKEN}"
offset = 0

def send(chat, text):
    requests.post(f"{URL}/sendMessage", data={"chat_id": chat, "text": text}, timeout=10)

def get_battery():
    try:
        out = subprocess.check_output(["termux-battery-status"], timeout=2)
        return json.loads(out).get("percentage", 100)
    except: return 100

def get_status():
    db = pathlib.Path.home() / "SHOGUN" / "shogun.db"
    if not db.exists():
        return "Database not found."
    con = __import__('sqlite3').connect(db)
    con.row_factory = __import__('sqlite3').Row
    cycle = con.execute("SELECT value FROM state WHERE key='cycle'").fetchone()["value"]
    equity = con.execute("SELECT cash, asset_amount FROM state WHERE key IN ('cash','asset_amount')").fetchall()
    # last observation price
    last = con.execute("SELECT price_usd, asset, quote_asset FROM observations ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return f"SHOGUN 1-OF-1\nCycle: {cycle}\nBattery: {get_battery()}%\nLast: {last['asset']}/{last['quote_asset']} price={last['price_usd']:.8f}"

print("SHOGUN Telegram bridge online.")
while True:
    try:
        r = requests.get(f"{URL}/getUpdates", params={"offset": offset, "timeout": 10}, timeout=15).json()
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            text = msg.get("text", "")
            chat = msg.get("chat", {}).get("id")
            if not chat or not text: continue
            if text.startswith("/status"):
                send(chat, get_status())
            elif text.startswith("/help"):
                send(chat, "Commands:\n/status – system status\n/help – help")
            else:
                send(chat, f"Received: {text}\nTry /status")
    except Exception as e:
        print(f"Telegram error: {e}")
        time.sleep(3)
