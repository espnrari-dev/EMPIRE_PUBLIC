#!/usr/bin/env python3
import requests, time
from datetime import datetime
from pathlib import Path
WALLET = "0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156"
LOG = Path.home() / "deep_recon" / "god.log"
print("👁️ GOD_HAND v3 - wallet enforcer")
while True:
    try:
        eth = 0
        try:
            r = requests.get(f"https://api.etherscan.io/api?module=account&action=balance&address={WALLET}&tag=latest", timeout=10).json()
            if r.get('result'): eth = int(r['result'])/1e18
        except: pass
        msg = f"[{datetime.now()}] GOD_HAND {WALLET[:8]} ETH={eth:.5f} READY"
        print(msg); LOG.write_text(msg+"\n")
    except Exception as e: print(e)
    time.sleep(25)
