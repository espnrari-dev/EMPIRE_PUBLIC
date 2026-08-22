#!/usr/bin/env python3
# BEACON - Original gap detector (restored)
import time
from datetime import datetime
from pathlib import Path
LOG = Path.home() / "deep_recon" / "beacon.log"
print("🔔 BEACON ARMED - scanning")
while True:
    LOG.write_text(f"[{datetime.now()}] BEACON alive\n")
    time.sleep(30)
