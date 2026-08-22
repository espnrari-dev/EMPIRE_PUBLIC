#!/data/data/com.termux/files/usr/bin/sh
echo "=== all KATANA PIDs ==="
pgrep -af KATANA.py || echo "none"
echo "killing individually"
for pid in $(pgrep -f KATANA.py); do
  echo "kill -9 $pid"
  kill -9 $pid
done
sleep 2
pgrep -af KATANA.py || echo "=== CLEAN - zero processes ==="
rm -f ~/deep_recon/katana.lock ~/deep_recon/katana.pid
