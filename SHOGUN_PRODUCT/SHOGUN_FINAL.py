import requests, time, json
from datetime import datetime
from pathlib import Path

LOG=Path.home()/"SHOGUN_FINAL_LOG.jsonl"
seen=set()
paper={} # addr -> {entry, chain}

CHAIN_MAP={"ethereum":"1","base":"8453","bsc":"56","solana":"9999"}

def is_honeypot(addr, chain):
    try:
        if chain not in ["ethereum","base","bsc"]:
            return False # skip sol check, allow
        cid=CHAIN_MAP.get(chain,"1")
        r=requests.get(f"https://api.honeypot.is/v2/IsHoneypot?address={addr}&chainID={cid}",timeout=8).json()
        return r.get('honeypotResult',{}).get('isHoneypot',False) or r.get('honeypotResult',{}).get('sellTax',0)>10
    except:
        return False

print("SHOGUN FINAL - BIRTH + LIQ + HONEYPOT + PAPER TRADE LIVE\n")

while True:
    try:
        births=requests.get("https://api.dexscreener.com/token-profiles/latest/v1",timeout=10).json()
        for t in births[:20]:
            addr=t.get('tokenAddress')
            chain=t.get('chainId','')
            if not addr or addr in seen: continue
            seen.add(addr)

            # LIQ CHECK
            try:
                d=requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}",timeout=6).json()
                pairs=d.get('pairs',[])
                if not pairs: continue
                liq=float(pairs[0].get('liquidity',{}).get('usd',0)or 0)
                price=float(pairs[0].get('priceUsd',0)or 0)
                if liq<5000 or price==0: continue

                # HONEYPOT CHECK
                if is_honeypot(addr, chain):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SKIP HONEYPOT {addr[:6]} liq ${liq:.0f}")
                    continue

                print(f"[{datetime.now().strftime('%H:%M:%S')}] REAL TARGET {chain} {addr[:8]} liq ${liq:.0f} price ${price:.8f}")
                paper[addr]={'entry':price,'chain':chain,'liq':liq,'born':datetime.now().isoformat()}
                LOG.write_text(json.dumps(paper[addr])+"\n") if False else None
                open(LOG,'a').write(json.dumps({'type':'buy','addr':addr,'chain':chain,'price':price,'liq':liq,'time':datetime.now().isoformat()})+"\n")

            except Exception as e:
                continue

        # PAPER TRADE CHECK - monitor all held
        for addr, info in list(paper.items()):
            try:
                d=requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}",timeout=6).json()
                p=float(d.get('pairs',[{}])[0].get('priceUsd',0)or 0)
                if not p: continue
                chg=(p-info['entry'])/info['entry']*100
                if chg>=30:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] PAPER WIN {addr[:6]} +{chg:.1f}% SELL")
                    open(LOG,'a').write(json.dumps({'type':'sell_win','addr':addr,'entry':info['entry'],'exit':p,'chg':chg})+"\n")
                    del paper[addr]
                elif chg<=-20:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] PAPER LOSS {addr[:6]} {chg:.1f}% STOP")
                    open(LOG,'a').write(json.dumps({'type':'sell_loss','addr':addr,'entry':info['entry'],'exit':p,'chg':chg})+"\n")
                    del paper[addr]
            except: pass

        print(f"[{datetime.now().strftime('%H:%M:%S')}] alive - seen {len(seen)} births - holding {len(paper)} paper positions")

    except Exception as e:
        print(f"alive error {e}")

    time.sleep(25)
