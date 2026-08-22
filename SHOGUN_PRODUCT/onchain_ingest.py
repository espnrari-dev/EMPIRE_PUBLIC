#!/usr/bin/env python3
"""Multi-source real on-chain ingestion for SHOGUN."""
import json
import os
import requests
from typing import Dict, Any, Optional

RPC_URLS = [
    "https://ethereum-rpc.publicnode.com",
    "https://1rpc.io/eth",
    "https://eth.drpc.org",
]

REQUEST_TIMEOUT = 15

ETHERSCAN_KEY = os.environ.get("ETHERSCAN_API_KEY", "").strip()
if not ETHERSCAN_KEY:
    key_file = os.path.expanduser("~/etherscan_key.txt")
    if os.path.exists(key_file):
        ETHERSCAN_KEY = open(key_file).read().strip()

COINGECKO_API = "https://api.coingecko.com/api/v3/simple/token_price/ethereum"

def rpc_call(method: str, params: list, rpc_index: int = 0) -> Optional[Dict[str, Any]]:
    if rpc_index >= len(RPC_URLS):
        return None
    url = RPC_URLS[rpc_index]
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if "result" in data:
                return data["result"]
    except Exception:
        pass
    return rpc_call(method, params, rpc_index + 1)

def get_eth_gas_price_gwei() -> Optional[float]:
    result = rpc_call("eth_gasPrice", [])
    if result:
        wei = int(result, 16)
        return wei / 1e9
    return None

def get_token_decimals(contract_address: str) -> Optional[int]:
    data = "0x313ce567"
    result = rpc_call("eth_call", [{"to": contract_address, "data": data}, "latest"])
    if result:
        try:
            return int(result, 16)
        except:
            return None
    return None

def get_token_total_supply(contract_address: str) -> Optional[int]:
    data = "0x18160ddd"
    result = rpc_call("eth_call", [{"to": contract_address, "data": data}, "latest"])
    if result:
        try:
            return int(result, 16)
        except:
            return None
    return None

def get_token_balance(contract_address: str, address: str) -> Optional[int]:
    if not address.startswith("0x"):
        address = "0x" + address
    addr_no0x = address[2:].lower().zfill(64)
    data = "0x70a08231" + addr_no0x
    result = rpc_call("eth_call", [{"to": contract_address, "data": data}, "latest"])
    if result:
        try:
            return int(result, 16)
        except:
            return None
    return None

def get_coingecko_token_data(contract_address: str) -> Optional[Dict[str, Any]]:
    params = {
        "contract_addresses": contract_address,
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true"
    }
    try:
        resp = requests.get(COINGECKO_API, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if contract_address.lower() in data:
                return data[contract_address.lower()]
    except Exception:
        pass
    return None

def get_etherscan_token_info(contract_address: str) -> Optional[Dict[str, Any]]:
    if not ETHERSCAN_KEY:
        return None
    url = "https://api.etherscan.io/api"
    params = {
        "module": "token",
        "action": "tokeninfo",
        "contractaddress": contract_address,
        "apikey": ETHERSCAN_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1" and "result" in data:
                return data["result"]
    except Exception:
        pass
    return None

def fetch_all_onchain(asset_address: str, price_usd: float) -> Dict[str, Any]:
    onchain = {
        "asset_address": asset_address,
        "gas_price_gwei": None,
        "total_supply": None,
        "decimals": None,
        "market_cap_from_supply": None,
        "holder_count": None,
        "coingecko_market_cap": None,
        "coingecko_volume_24h": None,
        "coingecko_price_change_24h": None,
        "etherscan_holders": None,
    }
    gas = get_eth_gas_price_gwei()
    if gas is not None:
        onchain["gas_price_gwei"] = gas
    dec = get_token_decimals(asset_address)
    if dec is not None:
        onchain["decimals"] = dec
        supply_raw = get_token_total_supply(asset_address)
        if supply_raw is not None:
            supply_human = supply_raw / (10 ** dec)
            onchain["total_supply"] = supply_human
            onchain["market_cap_from_supply"] = price_usd * supply_human
    cg = get_coingecko_token_data(asset_address)
    if cg:
        onchain["coingecko_market_cap"] = cg.get("usd_market_cap")
        onchain["coingecko_volume_24h"] = cg.get("usd_24h_vol")
        onchain["coingecko_price_change_24h"] = cg.get("usd_24h_change")
    es = get_etherscan_token_info(asset_address)
    if es:
        onchain["etherscan_holders"] = es.get("holders")
        if onchain["total_supply"] is None and es.get("totalSupply"):
            try:
                onchain["total_supply"] = float(es["totalSupply"])
            except:
                pass
    return onchain

if __name__ == "__main__":
    MOG = "0xaaee1a9723aadb7afa2810263653a34ba2c21c7a"
    price = 9.6e-8
    result = fetch_all_onchain(MOG, price)
    print(json.dumps(result, indent=2))
