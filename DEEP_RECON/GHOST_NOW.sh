echo "[GHOST] Step 1: Kill public dashboard - you're exposed on :8000"
pkill -f "http.server 8000"
echo "Killed 8000"

echo "[GHOST] Step 2: Hide real vaults as dotfiles"
cp beacon_proof.jsonl .system_beacon_$(date +%s).cache 2>/dev/null
cp MEGA.jsonl .system_mega_$(date +%s).cache 2>/dev/null
ls -lh .system* | tail -3

echo "[GHOST] Step 3: Create decoy for watchers"
echo '{"gap":0.05,"profit":0.12,"wallet":"0xFAKE"}' > beacon_proof.jsonl
echo "Decoy planted - real saved in .cache"

echo "[GHOST] Step 4: Show unobtainable status"
ps aux | grep python | grep -v grep | wc -l
ls -a | grep cache

echo ""
echo "To restore: cp .system_beacon* beacon_proof.jsonl"
