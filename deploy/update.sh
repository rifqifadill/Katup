#!/usr/bin/env bash
set -euo pipefail
cd -- "${1:?Repository path is required}"
test -d .git
test "$(git branch --show-current)" = deploy/katup-vps
test -z "$(git status --porcelain)" || { echo 'Working tree has changes; refusing deployment.' >&2; exit 1; }
git fetch origin deploy/katup-vps
git merge --ff-only origin/deploy/katup-vps
source deploy/env.sh
systemctl --user stop katup-simulation.service
python -m pip install -r deploy/requirements.lock.txt
python deploy/install-services.py
systemctl --user daemon-reload
systemctl --user stop katup-web katup-desktop katup-vnc katup-display
systemctl --user start katup-web
for attempt in {1..20}; do
    if curl --fail --silent --insecure https://127.0.0.1:8443/login >/dev/null; then
        echo 'Local HTTPS health check passed.'
        exit 0
    fi
    sleep 1
done
journalctl --user -u katup-web -n 30 --no-pager
exit 1
