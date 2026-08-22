import pathlib, json, time, subprocess
SRC = pathlib.Path.home() / "deep_recon" / "beacon_mega.jsonl"
LOG = pathlib.Path.home() / "deep_recon" / "katana.log"

print("=== BEFORE INJECT ===")
print(f"katana.log {len(LOG.read_text().splitlines())} lines")
before_claims = subprocess.check_output("~/ARCHON/archon status SHOGUN", shell=True, text=True)
print(before_claims)

for i in range(2):
    rec = {
        "token": "MOG",
        "gap_pct": 6.5+i,
        "net_gap_pct": 1.2,
        "profit_10k": 200+i,
        "dex": "uniswap",
        "cex": "coinbase",
        "hash": f"FINALPROOF{i}{int(time.time()*1000)}"
    }
    with open(SRC, "a") as f:
        f.write(json.dumps(rec)+"\n")
    print(f"injected {rec['hash'][:16]}")
    time.sleep(5)  # let KATANA loop pick it up

print("=== AFTER ===")
time.sleep(2)
print(f"katana.log {len(LOG.read_text().splitlines())} lines")
print(LOG.read_text().splitlines()[-3:])
print(subprocess.check_output("~/ARCHON/archon status SHOGUN", shell=True, text=True))
print(subprocess.check_output("~/ARCHON/archon audit | tail -12", shell=True, text=True))
