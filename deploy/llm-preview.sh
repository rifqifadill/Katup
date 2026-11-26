#!/usr/bin/env bash
set -euo pipefail
KATUP_PREVIEW_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$KATUP_PREVIEW_ROOT"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
export KATUP_PUBLIC_MODE=1
export KATUP_STANDALONE=1
export KATUP_STATE="${KATUP_STATE:-$KATUP_PREVIEW_ROOT/.runtime-llm}"
export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
if [ -x "$KATUP_PREVIEW_ROOT/.venv/bin/python" ]; then
  KATUP_PREVIEW_DEFAULT="$KATUP_PREVIEW_ROOT/.venv/bin/python"
else
  KATUP_PREVIEW_DEFAULT="$KATUP_PREVIEW_ROOT/../runtime/venv/bin/python"
fi
KATUP_PREVIEW_PYTHON="${KATUP_PYTHON:-$KATUP_PREVIEW_DEFAULT}"
exec "$KATUP_PREVIEW_PYTHON" -m uvicorn deploy.server:app --host 127.0.0.1 --port "${KATUP_PORT:-19010}" --no-access-log
