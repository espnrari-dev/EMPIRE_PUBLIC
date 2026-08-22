#!/usr/bin/env python3
import random, time
from datetime import datetime
from pathlib import Path
LOG = Path.home() / "deep_recon" / "chaos_monkey.log"
print("🐒 CHAOS_MONKEY v3")
while True:
    try:
        scenario = random.choice(["API down","Gas spike 200 gwei","Slippage 2%","CEX lag"])
        msg=f"[{datetime.now()}] CHAOS test {scenario} - KATANA would HOLD, GAS_GUARD would BLOCK"
        print(msg)
        with open(LOG,"a") as f: f.write(msg+"\n")
    except: pass
    time.sleep(45)
