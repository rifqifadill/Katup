#!/usr/bin/env bash
set -euo pipefail
rm -rf dist
mkdir -p dist/assets
cp deploy/index.html dist/index.html
cp deploy/assets/* dist/assets/
KATUP_API_BASE="${KATUP_API_BASE:-}" python3 - <<'PY'
import json
import os
from pathlib import Path

base = os.environ.get('KATUP_API_BASE', '').strip().rstrip('/')
Path('dist/assets/runtime-config.js').write_text(
    'window.KATUP_CONFIG = Object.freeze({apiBase: '
    + json.dumps(base)
    + '});\n',
    encoding='utf-8',
)
PY
