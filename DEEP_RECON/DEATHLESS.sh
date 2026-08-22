# Put in ~/.termux/boot/ -> auto start on boot
termux-wake-lock
nohup python -u BEACON.py > beacon.log 2>&1 &
nohup python -u BEACON_MEGA.py > beacon_mega.log 2>&1 &
nohup python -u VACUUM.py > vacuum.log 2>&1 &
nohup python -u LIVE_VACUUM.py > live_vacuum.log 2>&1 &
nohup python -u KATANA.py > katana.log 2>&1 &
nohup python -u GOD_HAND.py > god.log 2>&1 &
echo "Resurrected $(date) with 6 engines"
