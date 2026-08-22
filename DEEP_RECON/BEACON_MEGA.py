#!/usr/bin/env python3
import requests, time, json, hashlib
from datetime import datetime
from pathlib import Path
WALLET = "0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156"
FILE = str(Path.home() / "deep_recon/beacon_mega.jsonl")
MOG = "0xaaafAD35408b8F477E0d6c97F86AAE901E7fDEe7"
def get_dex_price():
    try:
        r=requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{MOG}", timeout=8, headers={"User-Agent":"Mozilla/5.0"}).json()
        pairs=r.get('pairs',[])
        if pairs:
            pairs.sort(key=lambda x: float(x.get('liquidity',{}).get('usd',0) or 0), reverse=True)
            return float(pairs[0]['priceUsd']), pairs[0]['dexId'], "dexscreener"
    except: pass
    try:
        r=requests.get(f"https://api.geckoterminal.com/api/v2/networks/eth/tokens/{MOG}/pools", timeout=8).json()
        data=r.get('data',[])
        if data: return float(data[0]['attributes']['base_token_price_usd']), data[0]['attributes']['name'], "gecko"
    except: pass
    # fixed coingecko with delay
    try:
        time.sleep(1)
        r=requests.get("https://api.coingecko.com/api/v3/simple/price?ids=mog-coin&vs_currencies=usd", timeout=10, headers={"User-Agent":"Mozilla/5.0"}).json()
        if 'mog-coin' in r: return float(r['mog-coin']['usd']), "coingecko", "coingecko"
    except Exception as e: print(f"CG wait {e}")
    return 0,"",""
def get_cex_price():
    try:
        r=requests.get("https://api.exchange.coinbase.com/products/MOG-USD/ticker", timeout=5).json()
        if r.get('price'): return float(r['price']), "coinbase"
    except: pass
    return 0,""
print("BEACON_MEGA v4 - ARMORED")
while True:
    dex_price,dex_name,src=get_dex_price()
    cex_price,cex_name=get_cex_price()
    if dex_price>0 and cex_price>0:
        gap=(cex_price-dex_price)/dex_price*100
        net=gap-0.4
        profit=10000*net/100
        h=hashlib.sha256(f"{dex_price}{cex_price}{gap}{datetime.now().isoformat()}".encode()).hexdigest()
        rec={"time":datetime.now().isoformat(),"token":"MOG","dex":f"{dex_name}({src})","dex_price":dex_price,"cex":cex_name,"cex_price":cex_price,"gap_pct":gap,"net_gap_pct":net,"profit_10k":profit,"hash":h,"wallet":WALLET}
        with open(FILE,"a") as f: f.write(json.dumps(rec)+"\n")
        tag="🚨 ARB" if net>0.5 else "gap"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} MOG {gap:.4f}% NET {net:.4f}% P=${profit:.2f} | {src}:{dex_name} vs {cex_name}")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] wait dex={dex_price} cex={cex_price}")
    time.sleep(6)
