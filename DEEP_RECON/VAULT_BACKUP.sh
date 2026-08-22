cp MEGA.jsonl .system_mega_$(date +%s).cache 2>/dev/null
cp beacon_proof.jsonl .system_beacon_$(date +%s).cache 2>/dev/null
cp vacuum.log vault_$(date +%Y%m%d).log 2>/dev/null
echo "Backup done: $(ls .system* vault* 2>/dev/null | wc -l) copies"
ls -lh .system* | tail -3
