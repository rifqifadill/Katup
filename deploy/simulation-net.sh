#!/usr/bin/env bash
set -euo pipefail
# A private network namespace keeps SUMO's wildcard TraCI socket off every host NIC.
ip link set lo up
if [[ -f "$KATUP_STATE/delay-ms" ]]; then
    delay_ms=$(cat "$KATUP_STATE/delay-ms")
    case "$delay_ms" in 100|200|1000) export KATUP_DELAY="$delay_ms" ;; *) echo 'Invalid GUI delay' >&2; exit 2 ;; esac
fi
exec python deploy/run_controller.py "$(cat "$KATUP_STATE/scenario")"
