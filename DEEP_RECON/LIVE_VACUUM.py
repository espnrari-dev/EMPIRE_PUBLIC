#!/usr/bin/env python3
import json, time
from pathlib import Path
from datetime import datetime
SRC = Path.home() / "deep_recon" / "beacon_mega.jsonl"
LOG = Path.home() / "deep_recon" / "live_vacuum.log"
print("🧹 LIVE_VACUUM v3 - on-chain hook armed")
while True:
    try:
        total=0; count=0
        if SRC.exists():
            with open(SRC) as f:
                for line in f.readlines()[-100:]:
                    try:
                        d=json.loads(line)
                        if d.get('net_gap_pct',0)>0.5:
                            total+=d.get('profit_10k',0); count+=1
                    except: pass
        msg=f"[{datetime.now()}] LIVE_VACUUM LIVE ${total:.2f} {count} arbs | wallet 0xcc9D READY TO VACUUM"
        print(msg); LOG.write_text(msg+"\n")
    except Exception as e: print(e)
    time.sleep(10)
