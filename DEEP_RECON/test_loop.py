import json, time, pathlib, subprocess, os
from datetime import datetime
SRC = pathlib.Path.home() / "deep_recon" / "beacon_mega.jsonl"
LOG = pathlib.Path.home() / "deep_recon" / "katana.log"
ARCHON = pathlib.Path.home() / "ARCHON" / "archon"

# clear for clean test
LOG.write_text("")
print(f"START katana.log lines={len(LOG.read_text().splitlines())}")

# inject 2 distinct gaps that will pass net>0.5
for i in range(2):
    rec = {
        "token": "MOG",
        "gap_pct": 5.9 + i,
        "net_gap_pct": 0.9,
        "profit_10k": 100 + i,
        "dex": "uniswap",
        "cex": "coinbase",
        "hash": f"testhash{i}{int(time.time()*1000)}"
    }
    with open(SRC, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"injected gap {rec['hash'][:8]}")

time.sleep(1)

# run KATANA v4.1 logic once (not infinite loop)
from archon_guard import can_execute
seen=set()
with open(SRC) as f:
    lines = f.readlines()[-5:]
    for line in lines:
        try:
            rec = json.loads(line)
            h = rec.get('hash')
            if h in seen or 'testhash' not in h: continue
            seen.add(h)
            gap_hash = h[0:8]
            allowed, archon_id = can_execute(rec['gap_pct'], 'MOG', gap_hash)
            if not allowed:
                print(f"blocked {h}")
                continue
            msg = f"[{datetime.now()}] ⚔️ EXECUTE MOG gap={rec['gap_pct']:.2f}% NET={rec['net_gap_pct']:.2f}% ARCHON={archon_id} P=${rec['profit_10k']:.2f}"
            print(msg)
            with open(LOG, "a") as logf:
                logf.write(msg + "\n")
        except Exception as e:
            print(f"err {e}")

print(f"END katana.log lines={len(LOG.read_text().splitlines())}")
print(LOG.read_text())
print(subprocess.check_output(f"{ARCHON} status SHOGUN", shell=True, text=True))
print(subprocess.check_output(f"{ARCHON} integrity", shell=True, text=True))
