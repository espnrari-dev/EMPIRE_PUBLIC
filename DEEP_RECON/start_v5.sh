#!/data/data/com.termux/files/usr/bin/sh
echo "=== preflight - must be zero ==="
pgrep -af KATANA.py || echo "zero - good"
rm -f ~/deep_recon/katana.lock ~/deep_recon/katana.pid
nohup python ~/deep_recon/KATANA.py > ~/deep_recon/katana_stdout.log 2>&1 &
sleep 2
echo "nohup \$! = $!"
echo "pidfile = $(cat ~/deep_recon/katana.pid)"
echo "pgrep = $(pgrep -f KATANA.py)"
echo "match? $([ "$(cat ~/deep_recon/katana.pid)" = "$(pgrep -f KATANA.py)" ] && echo YES || echo NO - MISMATCH)"
~/ARCHON/archon status SHOGUN
