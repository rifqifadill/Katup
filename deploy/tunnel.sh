#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
exec "$KATUP_RUNTIME/bin/cloudflared" tunnel --url https://127.0.0.1:8443 \
  --origin-ca-pool "$KATUP_STATE/tls.crt" --origin-server-name localhost \
  --no-autoupdate --loglevel info
