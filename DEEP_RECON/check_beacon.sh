#!/data/data/com.termux/files/usr/bin/sh
echo "=== 5.77 hash stability ==="
grep "5.77" ~/deep_recon/beacon_mega.jsonl | tail -10
echo "---"
echo "distinct hashes for same gap:"
grep "5.77" ~/deep_recon/beacon_mega.jsonl | tail -10 | python -c "import json,sys; hs=set(); [hs.add(json.loads(l).get('hash','')[:8]) or True for l in sys.stdin]; print(f'{len(hs)} distinct hashes')"
echo "=== restart KATANA ==="
pkill -9 -f KATANA.py
sleep 1
nohup python ~/deep_recon/KATANA.py > ~/deep_recon/katana_stdout.log 2>&1 &
echo $! > ~/deep_recon/katana.pid
echo "PID $(cat ~/deep_recon/katana.pid) - should now dedupe 5.77"
sleep 2
tail -3 ~/deep_recon/katana.log
~/ARCHON/archon status SHOGUN
