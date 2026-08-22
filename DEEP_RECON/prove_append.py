import pathlib, json, time, subprocess
from datetime import datetime
from archon_guard import can_execute

LOG = pathlib.Path.home() / "deep_recon" / "katana.log"
SRC = pathlib.Path.home() / "deep_recon" / "beacon_mega.jsonl"

# DON'T wipe live log - use copy for test
test_log = pathlib.Path.home() / "deep_recon" / "katana_test.log"
test_log.write_text(LOG.read_text())
print(f"test starts from {len(test_log.read_text().splitlines())} lines")

for i in range(2):
    allowed, archon_id = can_execute(6.1+i, 'MOG', f"proof{i}")
    if allowed:
        msg = f"[{datetime.now()}] PROOF EXECUTE {i} ARCHON={archon_id}"
        with open(test_log, "a") as f:
            f.write(msg+"\n")
        print(f"appended {i}")

print(f"test log now {len(test_log.read_text().splitlines())} lines")
print(test_log.read_text().splitlines()[-3:])
# prove real log untouched
print(f"live katana.log still {len(LOG.read_text().splitlines())} lines - not wiped by test")
