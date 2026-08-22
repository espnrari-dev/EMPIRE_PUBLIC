#!/usr/bin/env python3
import json, time
from pathlib import Path
from datetime import datetime
SRC=Path.home() / "deep_recon" / "beacon_mega.jsonl"
print("🏆 LEADERBOARD v3")
while True:
    try:
        total=0
        if SRC.exists():
            with open(SRC) as f:
                for l in f:
                    try: total+=json.loads(l).get('profit_10k',0)
                    except: pass
        print(f"[{datetime.now()}] LEADERBOARD Total potential ${total:.2f} - YOU ARE #1")
    except: pass
    time.sleep(20)
