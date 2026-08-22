#!/usr/bin/env python3
"""SHOGUN 1-of-1 Autonomous Intelligence Core (Final)."""
import hashlib, json, os, pathlib, sqlite3, subprocess, time, random
from datetime import datetime, timezone
import requests
import hashchain
import social_sentiment
import strategies

HOME = pathlib.Path.home()
BASE = HOME / "SHOGUN"
PRODUCT = BASE / "product"
WORKSPACE = BASE / "workspace"
DB_PATH = BASE / "shogun.db"
EVIDENCE_PATH = WORKSPACE / "evidence.jsonl"

NETWORK = "eth"
POOL = "0xc2eab7d33d3cb97692ecb231a5d0e4a649cb539d"
ASSET_ADDRESS = "0xaaee1a9723aadb7afa2810263653a34ba2c21c7a"
GECKO_URL = f"https://api.geckoterminal.com/api/v2/networks/{NETWORK}/pools/{POOL}?include=base_token,quote_token"
DEX_URL = f"https://api.dexscreener.com/latest/dex/pairs/ethereum/{POOL}"
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/token_price/ethereum"
RPC_URLS = ["https://ethereum-rpc.publicnode.com", "https://1rpc.io/eth", "https://eth.drpc.org"]
REQUEST_TIMEOUT = 15
CYCLE_INTERVAL = 60
ALPHA, GAMMA, EPSILON = 0.05, 0.95, 0.1
ACTIONS = ["buy", "sell", "hold"]
FEATURE_MIN = [0.0, 0.0, -50.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0]
FEATURE_MAX = [1e-5, 1e7, 50.0, 1e8, 1e7, 200.0, 1.0, 1.0, 1.0, 1.0, 1.0]

def connect_db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    con = connect_db()
    con.execute("""CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER NOT NULL,
        observed_at TEXT NOT NULL,
        source TEXT NOT NULL,
        asset TEXT NOT NULL,
        quote_asset TEXT NOT NULL,
        price_usd REAL NOT NULL,
        volume_24h_usd REAL,
        liquidity_usd REAL,
        price_change_24h REAL,
        gas_price_gwei REAL,
        total_supply REAL,
        market_cap_from_supply REAL,
        coingecko_market_cap REAL,
        coingecko_volume_24h REAL,
        coingecko_price_change_24h REAL,
        battery INTEGER,
        raw_hash TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        hash TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        confidence REAL,
        reward REAL,
        q_value REAL,
        state_hash TEXT,
        reason TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS q_table (
        state_key TEXT PRIMARY KEY,
        action_buy REAL DEFAULT 0,
        action_sell REAL DEFAULT 0,
        action_hold REAL DEFAULT 0,
        updated_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY,
        value TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cash REAL NOT NULL,
        asset_amount REAL NOT NULL,
        equity REAL NOT NULL,
        action TEXT NOT NULL)""")
    con.execute("INSERT OR IGNORE INTO state (key,value) VALUES ('cycle','0')")
    con.execute("INSERT OR IGNORE INTO state (key,value) VALUES ('last_hash',?)", (hashchain.GENESIS,))
    con.execute("INSERT OR IGNORE INTO state (key,value) VALUES ('cash','10000')")
    con.execute("INSERT OR IGNORE INTO state (key,value) VALUES ('asset_amount','0')")
    con.commit(); con.close()

def get_state(key):
    con = connect_db(); row = con.execute("SELECT value FROM state WHERE key=?",(key,)).fetchone(); con.close()
    return row["value"] if row else ""

def set_state(key, val):
    con = connect_db(); con.execute("INSERT OR REPLACE INTO state VALUES (?,?)",(key,val)); con.commit(); con.close()

def get_battery():
    try:
        out = subprocess.check_output(["termux-battery-status"], timeout=2)
        return json.loads(out).get("percentage", 100)
    except: return 100

def rpc_call(method, params, rpc_index=0):
    if rpc_index >= len(RPC_URLS): return None
    url = RPC_URLS[rpc_index]
    payload = {"jsonrpc":"2.0","method":method,"params":params,"id":1}
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and "result" in resp.json():
            return resp.json()["result"]
    except: pass
    return rpc_call(method, params, rpc_index+1)

def get_eth_gas_price_gwei():
    result = rpc_call("eth_gasPrice", [])
    if result:
        try: return int(result,16)/1e9
        except: pass
    return None

def get_token_decimals(addr):
    data = "0x313ce567"
    result = rpc_call("eth_call", [{"to":addr,"data":data},"latest"])
    if result:
        try: return int(result,16)
        except: pass
    return None

def get_token_total_supply(addr):
    data = "0x18160ddd"
    result = rpc_call("eth_call", [{"to":addr,"data":data},"latest"])
    if result:
        try: return int(result,16)
        except: pass
    return None

def get_coingecko_data(contract):
    params = {"contract_addresses":contract, "vs_currencies":"usd",
              "include_market_cap":"true","include_24hr_vol":"true","include_24hr_change":"true"}
    try:
        resp = requests.get(COINGECKO_API, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and contract.lower() in resp.json():
            return resp.json()[contract.lower()]
    except: pass
    return None

def fetch_market_data():
    errors = []
    try:
        resp = requests.get(GECKO_URL, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()["data"]
            attrs = data["attributes"]
            included = {item["id"]:item["attributes"].get("symbol","UNKNOWN") for item in resp.json().get("included",[]) if item["type"]=="token"}
            base_id = data["relationships"]["base_token"]["data"]["id"]
            quote_id = data["relationships"]["quote_token"]["data"]["id"]
            return {
                "source":"GeckoTerminal", "asset":included.get(base_id,"UNKNOWN"),
                "quote_asset":included.get(quote_id,"UNKNOWN"),
                "price_usd":float(attrs["base_token_price_usd"]),
                "volume_24h_usd":float(attrs.get("volume_usd",{}).get("h24",0) or 0),
                "liquidity_usd":float(attrs.get("reserve_in_usd",0) or 0),
                "price_change_24h":float(attrs.get("price_change_percentage",{}).get("h24",0) or 0),
                "raw":resp.json()}
    except Exception as e: errors.append(str(e))
    try:
        resp = requests.get(DEX_URL, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            pairs = resp.json().get("pairs",[])
            if pairs:
                pair = pairs[0]
                return {
                    "source":"DEXScreener", "asset":pair["baseToken"]["symbol"],
                    "quote_asset":pair["quoteToken"]["symbol"],
                    "price_usd":float(pair["priceUsd"]),
                    "volume_24h_usd":float(pair.get("volume",{}).get("h24",0) or 0),
                    "liquidity_usd":float(pair.get("liquidity",{}).get("usd",0) or 0),
                    "price_change_24h":float(pair.get("priceChange",{}).get("h24",0) or 0),
                    "raw":resp.json()}
    except Exception as e: errors.append(str(e))
    raise RuntimeError(f"No real data source: {'; '.join(errors)}")

def fetch_onchain_data(asset_address, price_usd):
    onchain = {"gas_price_gwei":None,"total_supply":None,"market_cap_from_supply":None,
               "coingecko_market_cap":None,"coingecko_volume_24h":None,"coingecko_price_change_24h":None}
    gas = get_eth_gas_price_gwei()
    if gas: onchain["gas_price_gwei"] = gas
    dec = get_token_decimals(asset_address)
    if dec:
        supply_raw = get_token_total_supply(asset_address)
        if supply_raw:
            supply = supply_raw / (10**dec)
            onchain["total_supply"] = supply
            onchain["market_cap_from_supply"] = price_usd * supply
    cg = get_coingecko_data(asset_address)
    if cg:
        onchain["coingecko_market_cap"] = cg.get("usd_market_cap")
        onchain["coingecko_volume_24h"] = cg.get("usd_24h_vol")
        onchain["coingecko_price_change_24h"] = cg.get("usd_24h_change")
    return onchain

def compute_features(obs, onchain):
    price = obs["price_usd"]; volume = obs["volume_24h_usd"] or 0
    change = obs["price_change_24h"] or 0
    mcap = onchain.get("coingecko_market_cap") or onchain.get("market_cap_from_supply") or 0
    gas = onchain.get("gas_price_gwei") or 0
    vol_mcap = volume / mcap if mcap > 0 else 0
    # Fetch real social sentiment (Reddit) for the asset
    symbol = obs.get("asset", "")
    sentiment = social_sentiment.get_social_sentiment(symbol)

    # Compute legendary investor scores from real data
    buffett = strategies.compute_buffett_score(obs, onchain, sentiment)
    munger  = strategies.compute_munger_score(obs, onchain, sentiment)
    fink    = strategies.compute_fink_score(obs, onchain, sentiment)

    feats = [price, volume, change, mcap, volume, gas, vol_mcap, sentiment, buffett, munger, fink]
    norm = []
    for i, val in enumerate(feats):
        lo, hi = FEATURE_MIN[i], FEATURE_MAX[i]
        norm.append(max(0.0, min(1.0, (val - lo) / (hi - lo))) if hi != lo else 0.0)
    return norm

def state_to_key(features):
    return ":".join(str(min(int(f * 4), 4)) for f in features)

def get_q_values(state_key):
    con = connect_db(); row = con.execute("SELECT * FROM q_table WHERE state_key=?",(state_key,)).fetchone(); con.close()
    if row: return {"buy":row["action_buy"], "sell":row["action_sell"], "hold":row["action_hold"]}
    return {"buy":0.0, "sell":0.0, "hold":0.0}

def update_q(state_key, action, reward, next_key):
    q = get_q_values(state_key); nq = get_q_values(next_key)
    q[action] += ALPHA * (reward + GAMMA * max(nq.values()) - q[action])
    con = connect_db()
    con.execute("""INSERT OR REPLACE INTO q_table (state_key, action_buy, action_sell, action_hold, updated_at)
                   VALUES (?,?,?,?,?)""",(state_key,q["buy"],q["sell"],q["hold"],datetime.now(timezone.utc).isoformat()))
    con.commit(); con.close()

def choose_action(state_key):
    if random.random() < EPSILON: return random.choice(ACTIONS)
    q = get_q_values(state_key); return max(q, key=q.get)

def get_portfolio():
    cash = float(get_state("cash") or 10000); asset_amt = float(get_state("asset_amount") or 0)
    return cash, asset_amt

def update_portfolio(cash, asset_amt):
    set_state("cash", str(cash)); set_state("asset_amount", str(asset_amt))

def execute_shadow_trade(action, price):
    cash, asset_amt = get_portfolio()
    if action == "buy" and cash > 0:
        spend = cash * 0.01; asset_amt += spend / price; cash -= spend
    elif action == "sell" and asset_amt > 0:
        sell_amt = asset_amt * 0.01; cash += sell_amt * price; asset_amt -= sell_amt
    equity = cash + asset_amt * price
    update_portfolio(cash, asset_amt)
    return cash, asset_amt, equity

def run_cycle():
    init_db()
    obs = fetch_market_data()
    onchain = fetch_onchain_data(ASSET_ADDRESS, obs["price_usd"])
    features = compute_features(obs, onchain)
    state_key = state_to_key(features)
    action = choose_action(state_key)

    cash_before, asset_before = get_portfolio()
    equity_before = cash_before + asset_before * obs["price_usd"]
    cash, asset_amt, equity = execute_shadow_trade(action, obs["price_usd"])
    reward = (equity - equity_before) / equity_before * 100 if equity_before > 0 else 0.0
    update_q(state_key, action, reward, state_key)

    prev_hash = get_state("last_hash")
    raw_hash = hashchain.raw_hash_of(obs["raw"])
    cycle = int(get_state("cycle") or 0) + 1
    current_hash = hashchain.chain_hash(prev_hash, raw_hash, cycle)

    con = connect_db()
    con.execute("""INSERT INTO observations (cycle, observed_at, source, asset, quote_asset, price_usd,
        volume_24h_usd, liquidity_usd, price_change_24h, gas_price_gwei, total_supply,
        market_cap_from_supply, coingecko_market_cap, coingecko_volume_24h, coingecko_price_change_24h,
        battery, raw_hash, prev_hash, hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cycle, datetime.now(timezone.utc).isoformat(), obs["source"], obs["asset"], obs["quote_asset"],
         obs["price_usd"], obs["volume_24h_usd"], obs["liquidity_usd"], obs["price_change_24h"],
         onchain.get("gas_price_gwei"), onchain.get("total_supply"), onchain.get("market_cap_from_supply"),
         onchain.get("coingecko_market_cap"), onchain.get("coingecko_volume_24h"), onchain.get("coingecko_price_change_24h"),
         get_battery(), raw_hash, prev_hash, current_hash))
    con.execute("""INSERT INTO decisions (cycle, timestamp, action, confidence, reward, q_value, state_hash, reason)
        VALUES (?,?,?,?,?,?,?,?)""",
        (cycle, datetime.now(timezone.utc).isoformat(), action, 0.5, reward,
         get_q_values(state_key)[action], hashlib.sha256(state_key.encode()).hexdigest(),
         f"{action} reward={reward:.4f}%"))
    con.execute("""INSERT INTO portfolio (timestamp, cash, asset_amount, equity, action)
        VALUES (?,?,?,?,?)""", (datetime.now(timezone.utc).isoformat(), cash, asset_amt, equity, action))
    con.commit(); con.close()

    set_state("cycle", str(cycle))
    set_state("last_hash", current_hash)

    evidence = {
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "obs": obs,
        "onchain": onchain,
        "features": features,
        "action": action,
        "reward": reward,
        "equity": equity,
        "raw_hash": raw_hash,
        "hash": current_hash
    }
    with EVIDENCE_PATH.open("a") as f:
        f.write(json.dumps(evidence) + "\n")

    return evidence

def main():
    init_db()
    print("SHOGUN CORE STARTED")
    while True:
        try:
            ev = run_cycle()
            print(f"[CYCLE {ev['cycle']}] {ev['obs']['source']} {ev['obs']['asset']} price={ev['obs']['price_usd']:.8f} action={ev['action']} reward={ev['reward']:.4f}% equity={ev['equity']:.2f}")
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(CYCLE_INTERVAL)

if __name__ == "__main__":
    main()
