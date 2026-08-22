#!/data/data/com.termux/files/usr/bin/sh
for pid in $(pgrep -f KATANA.py); do kill -9 $pid; done
sleep 1
pgrep -af KATANA.py || echo "zero - clean"
rm -f ~/deep_recon/katana.lock
nohup python ~/deep_recon/KATANA.py > ~/deep_recon/katana_stdout.log 2>&1 &
sleep 2
echo "pidfile $(cat ~/deep_recon/katana.pid) pgrep $(pgrep -f KATANA.py)"
~/ARCHON/archon status SHOGUN
