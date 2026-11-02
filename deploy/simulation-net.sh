#!/usr/bin/env bash
set -euo pipefail
# A private network namespace keeps SUMO's wildcard TraCI socket off every host NIC.
ip link set lo up
exec python deploy/run_controller.py "$(cat "$KATUP_STATE/scenario")"
