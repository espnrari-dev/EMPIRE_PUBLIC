import subprocess, sqlite3, os, json, re, hashlib, pathlib, time
ARCHON = os.path.expanduser("~/ARCHON/archon")
DB = os.path.expanduser("~/ARCHON/data/archon.db")
EVID_DIR = pathlib.Path.home() / "deep_recon" / "evidence_snapshots"
EVID_DIR.mkdir(parents=True, exist_ok=True)

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def req_id(project, code):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT r.requirement_id FROM requirements r JOIN projects p ON r.project_id=p.project_id WHERE p.name=? AND r.code=?", (project, code))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def integrity():
    return "PASS" in sh(f"{ARCHON} integrity")

def create_claim(rid, stmt, src):
    return sh(f'{ARCHON} claim add {rid} "{stmt}" "{src}"')

def add_evidence(cid, etype, loc, desc):
    return sh(f'{ARCHON} evidence add {cid} {etype} {loc} "{desc}"')

def validate(cid, res, validator, rationale):
    return sh(f'{ARCHON} validate {cid} {res} "{validator}" "{rationale}"')

def get_eth():
    try:
        god = open(os.path.expanduser("~/deep_recon/god.log")).read()
        m = re.search(r'ETH=([0-9.]+)', god)
        return float(m.group(1)) if m else 0.0
    except:
        return 0.0

def get_battery():
    try:
        out = sh("python ~/T_PRAO_L4/status.py 2>&1")
        m = re.search(r'Battery:\s*([0-9.]+)%', out)
        return float(m.group(1)) if m else 0.0
    except:
        return 0.0

def can_execute(gap_pct, token, gap_hash, rec=None, log_path=None, dedup_db=None, market_key=None):
    if not integrity():
        return False, None
    battery = get_battery()
    if battery < 15:
        return False, None
    eth = get_eth()
    r1 = req_id("SHOGUN", "R001")
    # snapshot first - always on disk even if archon fails later
    snap_path = None
    rec_sha = "none"
    if rec:
        try:
            rec_json = json.dumps(rec, sort_keys=True)
            rec_sha = hashlib.sha256(rec_json.encode()).hexdigest()
            snap_path = EVID_DIR / f"{int(time.time()*1000)}_{gap_hash}_{rec_sha[:8]}.json"
            snap_path.write_text(rec_json)
        except Exception as e:
            print(f"[ARCHON] snapshot write fail {e}")

    claim = create_claim(r1, f"KATANA {token} gap={gap_pct:.2f}% hash={gap_hash} eth={eth} batt={battery}%", "katana.log")
    snap_beacon = os.path.expanduser(f"~/deep_recon/evidence_snapshots/{int(__import__("time").time())}_beacon.jsonl"); __import__("shutil").copyfile(os.path.expanduser("~/deep_recon/beacon_mega.jsonl"), snap_beacon); add_evidence(claim, "LOG", snap_beacon, f"gap {gap_pct}% hash {gap_hash}")
    snap_katana = os.path.expanduser(f"~/deep_recon/evidence_snapshots/{int(__import__("time").time())}_katana.log"); __import__("shutil").copyfile(os.path.expanduser("~/deep_recon/katana.log"), snap_katana); add_evidence(claim, "LOG", snap_katana, f"intent {token}")
    add_evidence(claim, "RUNTIME", os.path.expanduser("~/T_PRAO_L4/status.py"), f"battery {battery}% eth {eth}")
    if snap_path and snap_path.exists():
        try:
            add_evidence(claim, "OBSERVATION", str(snap_path), f"record_sha={rec_sha}")
        except Exception as e:
            print(f"[ARCHON] snapshot evidence fail {e}")

    # ATOMIC: log + dedup must succeed BEFORE we PASS
    try:
        if log_path and market_key:
            msg = f"[{__import__('datetime').datetime.now()}] EXECUTE MOG gap={rec.get('gap_pct',0):.2f}% NET={rec.get('net_gap_pct',0):.2f}% ARCHON={claim} P=${rec.get('profit_10k',0):.2f} {rec.get('dex')}->{rec.get('cex')} KEY={market_key}"
            with open(log_path, "a") as lf:
                lf.write(msg + "\n")
                lf.flush()
                os.fsync(lf.fileno())
        if dedup_db and market_key:
            con = sqlite3.connect(dedup_db, timeout=30)
            con.execute("CREATE TABLE IF NOT EXISTS seen (market_key TEXT PRIMARY KEY, last_ts REAL)")
            con.execute("INSERT OR REPLACE INTO seen (market_key, last_ts) VALUES (?,?)", (market_key, time.time()))
            con.commit()
            con.close()
    except Exception as e:
        print(f"[ARCHON] ATOMIC log/dedup fail {e} - rolling back claim {claim} to FAIL")
        validate(claim, "FAIL", "GOD_HAND", f"ATOMIC_FAIL log/dedup {e}")
        return False, claim

    if eth < 0.001:
        validate(claim, "PASS", "GOD_HAND", f"PAPER eth={eth} battery={battery}%")
        return True, claim
    else:
        if eth > 0.001 and battery > 15:
            validate(claim, "PASS", "GOD_HAND", f"REAL eth={eth} battery={battery}%")
            return True, claim
        else:
            validate(claim, "FAIL", "GOD_HAND", f"BLOCKED eth={eth} battery={battery}%")
            return False, claim
