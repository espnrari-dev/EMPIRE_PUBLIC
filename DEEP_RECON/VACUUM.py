#!/usr/bin/env python3
# VACUUM v3 - Fixed to read beacon_mega.jsonl
import json, os, time
from datetime import datetime
from pathlib import Path
SRC = Path.home() / "deep_recon" / "beacon_mega.jsonl"
LOG = Path.home() / "deep_recon" / "vacuum.log"

def total_profit():
    total = 0.0
    count = 0
    if SRC.exists():
        with open(SRC) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('net_gap_pct',0) > 0.5:
                        total += data.get("profit_10k", 0)
                        count+=1
                except: pass
    return total, count

print("🧹 VACUUM v3 - reading beacon_mega.jsonl")
while True:
    profit, count = total_profit()
    now = datetime.now().isoformat()
    print(f"[{now}] Total ${profit:.2f} from {count} arbs")
    with open(LOG, "a") as log:
        log.write(f"{now} Total ${profit:.2f} count={count}\n")
    time.sleep(10)
