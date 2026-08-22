#!/data/data/com.termux/files/usr/bin/sh
pkill -9 -f KATANA.py
sleep 1
rm -f ~/deep_recon/katana.pid
nohup python ~/deep_recon/KATANA.py > ~/deep_recon/katana_stdout.log 2>&1 &
echo $! > ~/deep_recon/katana.pid
echo "KATANA v4.1 PID $(cat ~/deep_recon/katana.pid)"
sleep 1
ps aux | grep KATANA | grep -v grep
wc -l ~/deep_recon/katana.log
~/ARCHON/archon status SHOGUN
