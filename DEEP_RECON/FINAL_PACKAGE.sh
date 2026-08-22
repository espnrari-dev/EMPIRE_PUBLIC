#!/bin/bash
zip MOG_EMPIRE.zip BEACON.py DASHBOARD.py VERIFY.py beacon_proof.jsonl index.html README.txt -q
ls -lh MOG_EMPIRE.zip
echo ""
echo "=== WHAT'S INSIDE ==="
unzip -l MOG_EMPIRE.zip
echo ""
echo "Send MOG_EMPIRE.zip to buyer"
echo "Buyer runs: python BEACON.py"
