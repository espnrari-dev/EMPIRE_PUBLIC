#!/data/data/com.termux/files/usr/bin/sh
echo "=== PS KATANA ==="
ps aux | grep -i katana | grep -v grep || pgrep -a KATANA || echo "no ps"
echo "=== KILLING OLD KATANA ==="
pkill -9 -f KATANA.py
pkill -9 -f katana
sleep 1
ps aux | grep -i katana | grep -v grep || echo "killed - none running"
echo "=== CLEAN beacon_mega.jsonl testhash ==="
BEACON=~/deep_recon/beacon_mega.jsonl
BEFORE=$(wc -l < $BEACON)
grep -v "testhash" $BEACON > $BEACON.tmp && mv $BEACON.tmp $BEACON
AFTER=$(wc -l < $BEACON)
echo "beacon $BEFORE -> $AFTER"
echo "=== katana.log current ==="
wc -l ~/deep_recon/katana.log
tail -5 ~/deep_recon/katana.log
echo "=== ARCHON ==="
~/ARCHON/archon status SHOGUN
~/ARCHON/archon integrity
