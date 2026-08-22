#!/usr/bin/env python3
import json, os, signal, sys, time, traceback

BASE = os.path.expanduser("~")
RECON = os.path.join(BASE, "deep_recon")
OS_ROOT = os.path.join(BASE, "SHOGUN_OS")
RUN = os.path.join(OS_ROOT, "run")
LOGS = os.path.join(OS_ROOT, "logs")

sys.path.insert(0, RECON)
from database import initialize, verify, connect, record_event

PID_FILE = os.path.join(RUN, "katana.pid")
HEARTBEAT = os.path.join(RUN, "katana.heartbeat")
INTERVAL = 5
STOP = False

def log(message):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, "katana.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(message) + "\n")

def heartbeat():
    payload = {"component": "KATANA", "pid": os.getpid(), "timestamp": time.time(),
               "mode": "MONITOR", "execution": "NO_EXECUTION_BY_DESIGN"}
    tmp = HEARTBEAT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True)
    os.replace(tmp, HEARTBEAT)

def shutdown(signum, frame):
    global STOP
    STOP = True

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

def run():
    os.makedirs(RUN, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    initialize()
    verify()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    log("KATANA STARTED PID=" + str(os.getpid()))
    record_event("KATANA", "START", time.time())
    heartbeat()
    while not STOP:
        try:
            con = connect()
            try:
                con.execute("SELECT market_key, last_ts FROM seen ORDER BY market_key LIMIT 100").fetchall()
            finally:
                con.close()
            heartbeat()
        except Exception:
            log("LOOP ERROR:\n" + traceback.format_exc())
            try:
                record_event("KATANA", "ERROR", time.time(), detail=traceback.format_exc())
            except Exception:
                pass
        time.sleep(INTERVAL)
    record_event("KATANA", "STOP", time.time())
    log("KATANA STOPPED PID=" + str(os.getpid()))
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass

if __name__ == "__main__":
    try:
        run()
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass
        sys.exit(1)
