#!/usr/bin/env python

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from T_PRAO_L4.core.state import load

MAX_HEARTBEAT_AGE = 10


def main():
    state = load()

    heartbeat = state.get("heartbeat")

    if heartbeat is None:
        print("WATCHDOG: NO_HEARTBEAT")
        raise SystemExit(1)

    age = time.time() - float(heartbeat)

    print("T-PRAO L4 WATCHDOG")
    print("==================")
    print(f"Status: {state.get('status')}")
    print(f"Heartbeat Age: {age:.2f}s")
    print(f"Cycles: {state.get('cycles')}")
    print(f"Data: {state.get('data_status')}")
    print(f"Updated: {state.get('updated_at')}")

    if age > MAX_HEARTBEAT_AGE:
        print("VERDICT: STALE")
        raise SystemExit(2)

    print("VERDICT: HEALTHY")


if __name__ == "__main__":
    main()
