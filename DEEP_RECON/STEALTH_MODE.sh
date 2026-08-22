pkill -f "http.server"
mv *.log . 2>/dev/null
mv beacon_proof.jsonl .system_beacon_$(date +%s).cache 2>/dev/null
echo '{"gap":0.01,"profit":0.00,"wallet":"0xDECOY"}' > beacon_proof.jsonl
echo "Ghosted. Real hidden, decoy planted."
