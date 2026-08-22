import json
from hashchain import GENESIS, chain_hash

prev = GENESIS
path = "/data/data/com.termux/files/home/SHOGUN/workspace/evidence.jsonl"

with open(path) as f:
    for line in f:
        rec = json.loads(line)
        expected = chain_hash(prev, rec["raw_hash"], rec["cycle"])
        assert expected == rec["hash"], f"Chain broken at cycle {rec['cycle']}"
        prev = rec["hash"]

print("Hash chain intact.")
