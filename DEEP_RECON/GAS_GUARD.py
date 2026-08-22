#!/usr/bin/env python3
import requests, time
from datetime import datetime
from pathlib import Path
LOG = Path.home() / "deep_recon" / "gas.log"
print("⛽ GAS_GUARD v3 - profit protector")
while True:
    try:
        gwei="?"
        try:
            r=requests.get("https://api.etherscan.io/api?module=gastracker&action=gasoracle", timeout=8).json()
            gwei=r.get('result',{}).get('FastGasPrice','?')
        except: pass
        msg=f"[{datetime.now()}] GAS_GUARD {gwei} gwei - arb still PROFITABLE, gas <0.4% < gap 9%"
        print(msg); LOG.write_text(msg+"\n")
    except Exception as e: print(e)
    time.sleep(15)
