#!/bin/bash

ROOT="$HOME/SHOGUN_OS"
DEEP_RECON="$HOME/deep_recon"

LOG="$ROOT/08_INTELLIGENCE/live_loop.log"
V4="$ROOT/08_INTELLIGENCE/v4_complete_observations.json"
TMP_OUT="$ROOT/08_INTELLIGENCE/v6_out.txt"

echo "=== LIVE START $(date -u) ===" | tee -a "$LOG"

count=0

while true; do
    count=$((count + 1))

    echo "" | tee -a "$LOG"
    echo "[$(date -u)] LOOP $count" | tee -a "$LOG"

    ADAPTER_OUT=$(
        python3 "$DEEP_RECON/adapters/adapter_v2_complete.py" 2>&1
    )
    ADAPTER_RC=$?

    echo "$ADAPTER_OUT" | tail -5 | tee -a "$LOG"

    if [ "$ADAPTER_RC" -eq 0 ]; then
        echo "ADAPTER_STATUS=OK" | tee -a "$LOG"
    else
        echo "ADAPTER_STATUS=DEGRADED rc=$ADAPTER_RC" | tee -a "$LOG"
    fi

    python3 \
        "$ROOT/08_INTELLIGENCE/reasoning_v6_live.py" \
        > "$TMP_OUT" 2>&1

    REASONING_RC=$?

    cat "$TMP_OUT" | tee -a "$LOG"

    if [ "$REASONING_RC" -eq 0 ]; then
        echo "REASONING_STATUS=OK" | tee -a "$LOG"
    else
        echo "REASONING_STATUS=ERROR rc=$REASONING_RC" | tee -a "$LOG"
    fi

    V4C=$(
        python3 -c "
import json
with open('$V4') as f:
    data = json.load(f)
print(len(data))
" 2>/dev/null
    )

    if [ -z "$V4C" ]; then
        V4C=0
    fi

    ENGINE_COUNT=0

    for engine in \
        KATANA.py \
        BEACON.py \
        BEACON_MEGA.py \
        VACUUM.py \
        LIVE_VACUUM.py \
        TAI_CHI.py \
        GOD_HAND.py
    do
        if pgrep -f "$engine" >/dev/null; then
            ENGINE_COUNT=$((ENGINE_COUNT + 1))
        fi
    done

    echo \
        "METRICS: loop=$count v4=$V4C engines=$ENGINE_COUNT/7 adapter_rc=$ADAPTER_RC reasoning_rc=$REASONING_RC" \
        | tee -a "$LOG"

    sleep 60
done
