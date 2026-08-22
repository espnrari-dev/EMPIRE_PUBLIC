#!/data/data/com.termux/files/usr/bin/sh
echo "ARCHON chain:"
~/ARCHON/archon integrity
echo ""
echo "Snapshot files on disk vs ARCHON evidence digests:"
for f in ~/deep_recon/evidence_snapshots/*.json; do
  sha=$(sha256sum "$f" | cut -d' ' -f1)
  echo "$sha  $(basename $f)"
done | tail -5
echo ""
echo "If a snapshot was edited after claim, its sha would not match ARCHON evidence table - that check is the last unverified claim"
~/ARCHON/archon status SHOGUN
