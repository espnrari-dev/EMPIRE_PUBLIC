./EMPIRE_SNAPSHOT.sh > EMPIRE_PROOF_$(date +%Y%m%d_%H%M).txt
cat EMPIRE_PROOF_*.txt | tail -30
