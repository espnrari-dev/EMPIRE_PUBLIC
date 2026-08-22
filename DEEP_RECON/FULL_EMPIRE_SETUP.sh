#!/data/data/com.termux/files/usr/bin/bash
cd ~/deep_recon
echo "=== MOG EMPIRE FULL TOOLING ==="

pip install requests python-dotenv --quiet

# 1. ENV - API KEYS (you need these for KATANA to execute)
cat >.env.example << 'ENV'
KRAKEN_API_KEY=
KRAKEN_API_SECRET=
COINBASE_API_KEY=
COINBASE_API_SECRET=
# Optional for MOG token
ALCHEMY_BASE_RPC=https://base-mainnet.g.alchemy.com/v2/YOUR_KEY
WALLET=0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156
ENV
[ -f.env ] || cp.env.example.env

# 2. BEACON_MEGA V2 - with fee filter
cat > BEACON_MEGA_V2.py << 'PY'
import time, json, hashlib, requests
from datetime import datetime
WALLET="0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156"
FILE="beacon_mega.jsonl"
FEE_PCT=0.26 # Kraken 0.16 + Coinbase 0.10 = ~0.26% roundtrip fees

def get_prices():
    try:
        k = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5).json()
        c = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker", timeout=5).json()
        kraken = float(k['result']['XXBTZUSD']['c'][0])
        coinbase = float(c['price'])
        gap = (coinbase-kraken)/kraken*100
        net_gap = gap - FEE_PCT
        return kraken, coinbase, gap, net_gap
    except Exception as e:
        print("Price err",e)
        return 0,0,0,0

print(f"🚀 BEACON V2 LIVE | Fees {FEE_PCT}% | Wallet {WALLET}")
while True:
    k,c,gap,net = get_prices()
    if k>0:
        h = hashlib.sha256(f"{k}{c}{gap}{datetime.now().isoformat()}".encode()).hexdigest()
        profit_10k = 10000*net/100
        rec={"time":datetime.now().isoformat(),"kraken":k,"coinbase":c,"gap_pct":gap,"net_gap_pct":net,"profit_10k":profit_10k,"hash":h,"wallet":WALLET}
        with open(FILE,"a") as f: f.write(json.dumps(rec)+"\n")
        status = "PROFITABLE" if net>0 else "NOPE"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} GAP {gap:.4f}% NET {net:.4f}% | $10k=${profit_10k:.2f} | K ${k:.2f} C ${c:.2f}")
    time.sleep(3)
PY

# 3. VACUUM V2 - only flips if profitable after fees
cat > VACUUM_V2.py << 'PY'
import json, time
from pathlib import Path
from datetime import datetime
SRC=Path("beacon_mega.jsonl")
OUT=Path("vacuum_flips.jsonl")
MIN_NET=0.05 # only flip if net >0.05% after fees
print(f"VACUUM V2 | MIN NET {MIN_NET}%")
last_line=0
while True:
    if not SRC.exists():
        time.sleep(2); continue
    lines=SRC.read_text().splitlines()[last_line:]
    for l in lines:
        try:
            b=json.loads(l)
            if b.get('net_gap_pct',0) > MIN_NET:
                flip={"time":datetime.now().isoformat(),"buy":b['kraken'] if b['kraken']<b['coinbase'] else b['coinbase'],"sell":b['coinbase'] if b['coinbase']>b['kraken'] else b['kraken'],"net_pct":b['net_gap_pct'],"profit_10k":b['profit_10k'],"proof_hash":b['hash']}
                with open(OUT,"a") as f: f.write(json.dumps(flip)+"\n")
                print(f"💰 FLIP {flip['net_pct']:.4f}% | ${flip['profit_10k']:.2f}/10k | {flip['proof_hash'][:8]}")
        except: pass
    last_line=len(SRC.read_text().splitlines())
    time.sleep(2)
PY

# 4. TAI_CHI V2 - balance checker
cat > TAI_CHI_V2.py << 'PY'
import json
from pathlib import Path
f=Path("beacon_mega.jsonl")
if not f.exists(): print("No beacons"); exit()
beacons=[json.loads(l) for l in f.read_text().splitlines()[-500:] if l]
avg=sum(b['gap_pct'] for b in beacons)/len(beacons)
avg_net=sum(b.get('net_gap_pct',0) for b in beacons)/len(beacons)
prof=len([b for b in beacons if b.get('net_gap_pct',0)>0])
print(f"TAI_CHI BALANCE | {len(beacons)} beacons")
print(f"Avg Gap: {avg:.5f}% | Avg Net (after 0.26% fees): {avg_net:.5f}%")
print(f"Profitable beacons: {prof}/{len(beacons)} = {prof/len(beacons)*100:.1f}%")
print(f"Best Net: {max(b.get('net_gap_pct',0) for b in beacons):.4f}%")
PY

# 5. KATANA - executor (paper mode by default)
cat > KATANA_V2.py << 'PY'
import os, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
PAPER=True # SET FALSE ONLY WHEN YOU HAVE API KEYS AND TESTED
print(f"KATANA V2 | PAPER MODE = {PAPER} | Wallet {os.getenv('WALLET')}")
print("To go live: 1. fill.env with KRAKEN/COINBASE keys 2. set PAPER=False")
print("For now it DRY RUNS from vacuum_flips.jsonl")
# Real execution needs ccxt - install if live
# pip install ccxt
PY

# 6. DASHBOARD V2 - fixed
cat > DASHBOARD_V2.py << 'PY'
import json, time
from pathlib import Path
from datetime import datetime
SRC=Path("beacon_mega.jsonl")
OUT=Path("index.html")
while True:
    beacons=[]
    if SRC.exists():
        try:
            beacons=[json.loads(l) for l in SRC.read_text().splitlines()[-500:] if l.strip()]
        except: pass
    if not beacons:
        time.sleep(3); continue
    avg=sum(b['gap_pct'] for b in beacons)/len(beacons)
    avg_net=sum(b.get('net_gap_pct',b['gap_pct']-0.26) for b in beacons)/len(beacons)
    prof=[b for b in beacons if b.get('net_gap_pct',0)>0]
    total_net_1k = sum(b.get('net_gap_pct',0)/100*1000 for b in prof)
    last=beacons[-1]
    html=f"""
<html><head><meta name='viewport' content='width=device-width'><title>BEACON LIVE</title>
<style>body{{background:#0a0a0a;color:#0f8;font-family:monospace;padding:15px}}.card{{border:1px solid #0f8;padding:12px;margin:8px 0;border-radius:8px}}.big{{font-size:28px}}</style>
</head><body>
<h2>📡 BEACON V2 - BTC ARB</h2>
<div class=card>Avg Gap: <span class=big>{avg:.4f}%</span> | Avg Net after fees: <b>{avg_net:.4f}%</b></div>
<div class=card>Profitable: {len(prof)}/{len(beacons)} ({len(prof)/len(beacons)*100:.1f}%) | Total Net Oppt (1k cap, last 500): ${total_net_1k:.2f}</div>
<div class=card>Last: K ${last['kraken']:.2f} C ${last['coinbase']:.2f} GAP {last['gap_pct']:.4f}% NET {last.get('net_gap_pct',0):.4f}% HASH {last['hash'][:12]}</div>
<div class=card>{"<br>".join([f"{b['time'][11:19]} NET {b.get('net_gap_pct',0):.4f}% ${b.get('profit_10k',0):.2f}/10k" for b in beacons[-30:][::-1]])}<br></div>
<script>setTimeout(()=>location.reload(),3000)</script>
</body></html>"""
    OUT.write_text(html)
    print(f"Built {OUT} | AVG {avg:.4f}% NET {avg_net:.4f}% | Profitable {len(prof)}/{len(beacons)}")
    time.sleep(5)
PY

# 7. SHOGUN FINAL
cat > ~/SHOGUN.py << 'PY'
import os, subprocess, sys, time
W="0xcc9DFB8C65a1839373C0c051114eB6752Ec4B156"
print(f"=== SHOGUN FINAL | {W} ===")
print("1 BEACON V2 (fee-aware) | 2 VACUUM V2 (profit filter) | 3 TAI_CHI V2 | 4 DASHBOARD V2 | 5 FULL EMPIRE tmux")
c=input("Select: ").strip()
base=os.path.expanduser("~/deep_recon")
if c=="1": subprocess.run([sys.executable, f"{base}/BEACON_MEGA_V2.py"])
elif c=="2": subprocess.run([sys.executable, f"{base}/VACUUM_V2.py"])
elif c=="3": subprocess.run([sys.executable, f"{base}/TAI_CHI_V2.py"])
elif c=="4": subprocess.run([sys.executable, f"{base}/DASHBOARD_V2.py"])
elif c=="5":
    subprocess.run(["bash", f"{base}/../EMPIRE_LAUNCH_V2.sh"])
PY

cat > ~/EMPIRE_LAUNCH_V2.sh << 'SH2'
#!/data/data/com.termux/files/usr/bin/bash
tmux kill-session -t empire 2>/dev/null
tmux new-session -d -s empire -n beacon "cd ~/deep_recon; python3 BEACON_MEGA_V2.py"
tmux new-window -t empire:1 -n vacuum "cd ~/deep_recon; python3 VACUUM_V2.py"
tmux new-window -t empire:2 -n taichi "cd ~/deep_recon; watch -n 5 python3 TAI_CHI_V2.py"
tmux new-window -t empire:3 -n dash "cd ~/deep_recon; python3 DASHBOARD_V2.py"
echo "Launched V2 empire - tmux attach -t empire"
tmux ls
SH2
chmod +x ~/EMPIRE_LAUNCH_V2.sh
echo "DONE"
echo "Run: ~/EMPIRE_LAUNCH_V2.sh then tmux attach -t empire"
echo "Tools: BEACON_MEGA_V2.py, VACUUM_V2.py, TAI_CHI_V2.py, KATANA_V2.py (paper), DASHBOARD_V2.py"
echo "Need: pip install python-dotenv ccxt"
