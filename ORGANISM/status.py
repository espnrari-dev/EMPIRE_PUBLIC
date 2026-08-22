#!/usr/bin/env python

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from T_PRAO_L4.core.state import load


def main():
    state = load()

    print("T-PRAO L4 STATUS")
    print("================")
    print(f"Mode: {state.get('mode')}")
    print(f"Status: {state.get('status')}")
    print(f"Asset: {state.get('asset')}")
    print(f"Network: {state.get('network')}")
    print(f"Market Source: {state.get('market_source')}")
    print(f"Market Pool: {state.get('market_pool')}")
    print(f"Price: {state.get('price')}")
    print(f"Previous Price: {state.get('previous_price')}")
    print(f"Price Delta: {state.get('price_delta')}")
    print(f"Battery: {state.get('battery')}%")
    print(f"Battery Source: {state.get('battery_source')}")
    print(f"Data Valid: {state.get('data_valid')}")
    print(f"Data Status: {state.get('data_status')}")
    print(f"Data Age: {state.get('data_age_seconds')}")
    print(f"Cycles: {state.get('cycles')}")
    print(f"Previous Hash: {state.get('previous_hash')}")
    print(f"Last Hash: {state.get('last_hash')}")
    print(f"Heartbeat: {state.get('heartbeat')}")
    print(f"Updated: {state.get('updated_at')}")


if __name__ == "__main__":
    main()
