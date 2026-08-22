#!/usr/bin/env python3
"""
VOICE_SHOGUN – Daemon with PID lock (no more dupes).
"""
import os, sys, time, fcntl

PID_FILE = "/data/data/com.termux/files/home/SHOGUN_OS/08_INTELLIGENCE/voice.pid"
LOG_FILE = "/data/data/com.termux/files/home/SHOGUN_OS/08_INTELLIGENCE/voice.log"

def acquire_lock():
    try:
        with open(PID_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.write(str(os.getpid()))
            f.flush()
            return True
    except:
        return False

def main():
    if not acquire_lock():
        # Already running, exit quietly
        sys.exit(0)
    with open(LOG_FILE, 'a') as log:
        log.write(f"VOICE_SHOGUN daemon started (PID {os.getpid()})\n")
    while True:
        time.sleep(60)
        with open(LOG_FILE, 'a') as log:
            log.write("VOICE_HEARTBEAT\n")

if __name__ == "__main__":
    main()
