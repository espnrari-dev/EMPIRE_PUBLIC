#!/bin/bash
# Quick health check for the 5 things you listed
echo "=== LIVING SYSTEM CHECK $(date) ==="
echo ""
echo "1. Does loop survive for hours?"
ps aux | grep SHOGUN_LIVE_OPERATIONAL | grep -v grep && echo "  YES - running" || echo "  NO - not running"
tail -5 ~/SHOGUN_OS/08_INTELLIGENCE/live_loop.log
echo ""
echo "2. Do observations keep updating?"
ls -lh ~/SHOGUN_OS/08_INTELLIGENCE/v4_complete_observations.json
echo "  age: $(( $(date +%s) - $(stat -c %Y ~/SHOGUN_OS/08_INTELLIGENCE/v4_complete_observations.json) ))s ago"
echo ""
echo "3. Does ledger continue growing?"
wc -l ~/SHOGUN_OS/08_INTELLIGENCE/decision_ledger.json 2>/dev/null; python3 -c "import json; print(f'  decisions: {len(json.load(open(\"~/SHOGUN_OS/08_INTELLIGENCE/decision_ledger.json\")))}')" 2>/dev/null
echo ""
echo "4. Do decisions change when sensors change?"
cat ~/SHOGUN_OS/08_INTELLIGENCE/v6_live_proof.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  last profit: {d[\"real_readings\"][\"beacon_profit\"]} gap: {d[\"real_readings\"][\"beacon_gap\"]}'); [print(f'   - {x[\"action\"]}: {x[\"reason\"][:60]}') for x in d['decisions']]"
echo ""
echo "5. Does RESURRECT recover without manual?"
ps aux | grep RESURRECT | grep -v grep
echo "  engines_live: $(ps aux | grep -E 'KATANA|BEACON_MEGA|VACUUM' | grep -v grep | wc -l)/7"
