#!/usr/bin/env python3
import json, time
from pathlib import Path
from datetime import datetime
SRC = Path.home() / "deep_recon" / "beacon_mega.jsonl"
LOG = Path.home() / "deep_recon" / "tai_chi.log"
print("☯️ TAI_CHI v3 - risk governor")
while True:
    try:
        if SRC.exists():
            with open(SRC) as f:
                try: rec = json.loads(f.readlines()[-1])
                except: rec={}
            net = rec.get('net_gap_pct',0)
            if net>8: size, risk="10000","SEND IT"
            elif net>5: size, risk="5000","LARGE"
            elif net>2: size, risk="2000","MED"
            elif net>0.5: size, risk="1000","SMALL"
            else: size, risk="0","HOLD"
            msg=f"[{datetime.now()}] TAI_CHI NET={net:.2f}% -> {risk} ${size}"
            print(msg); LOG.write_text(msg+"\n")
    except Exception as e: print(e)
    time.sleep(8)
