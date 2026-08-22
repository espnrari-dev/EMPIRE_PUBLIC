#!/data/data/com.termux/files/usr/bin/sh
echo "=== wait for next real gap (30s) ==="
sleep 35
echo "=== katana.log ==="
tail -3 ~/deep_recon/katana.log
echo "=== snapshots ==="
ls -lt ~/deep_recon/evidence_snapshots/ | head -5
echo "=== dedup db ==="
sqlite3 ~/deep_recon/katana_seen.db "SELECT market_key, datetime(last_ts,'unixepoch','localtime') FROM seen ORDER BY last_ts DESC LIMIT 5;"
echo "=== archon ==="
~/ARCHON/archon status SHOGUN
~/ARCHON/archon audit | tail -6
