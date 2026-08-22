#!/usr/bin/env python

import pathlib
import sys
import time

from core.cycle import execute_cycle


ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
INTERVAL = 2


def main():
    print(
        "T-PRAO L4 RUNTIME ONLINE",
        flush=True
    )

    while True:
        try:
            state = execute_cycle()

            print(
                "T-PRAO L4 LIVE | "
                f"STATUS={state.get('status')} | "
                f"BATT={state.get('battery')}% | "
                f"ASSET={state.get('asset')} | "
                f"PRICE={state.get('price')} | "
                f"CYCLES={state.get('cycles')} | "
                f"DATA={state.get('data_status')} | "
                f"HASH={state.get('last_hash')}",
                flush=True
            )

        except Exception as exc:
            print(
                "T-PRAO L4 RUNTIME ERROR | "
                f"{type(exc).__name__}: {exc}",
                flush=True
            )

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
