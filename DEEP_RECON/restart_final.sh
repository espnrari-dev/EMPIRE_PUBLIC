#!/data/data/com.termux/files/usr/bin/sh
nohup python -u ~/deep_recon/KATANA.py > ~/deep_recon/katana_stdout.log 2>&1 &
sleep 2
echo "pidfile $(cat ~/deep_recon/katana.pid) pgrep $(pgrep -f KATANA.py)"
echo "stdout should now show polls:"
tail -5 ~/deep_recon/katana_stdout.log
