#!/data/data/com.termux/files/usr/bin/bash
mkdir -p ~/ARCHON/data
LOCK=~/ARCHON/data/katana.lock
exec 200>"$LOCK"
flock -n 200 || exit 0
echo $$ > ~/ARCHON/data/katana.pid
python $HOME/deep_recon/KATANA.py
