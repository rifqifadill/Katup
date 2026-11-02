#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$KATUP_REPO"
case "$1" in
 display) cd "$KATUP_RUNTIME/root/usr/bin"; exec ./Xvfb-local :95 -screen 0 1280x800x24 -nolisten tcp -auth "$XAUTHORITY" +extension GLX +render -noreset ;;
 desktop) exec openbox --sm-disable ;;
 vnc) exec x11vnc -display :95 -auth "$XAUTHORITY" -rfbauth "$KATUP_STATE/vnc.pass" -rfbport 5905 -listen 127.0.0.1 -no6 -noipv6 -rfbportv6 -1 -forever -shared -noxdamage -noshm ;;
 web) exec python -m uvicorn deploy.server:app --host 0.0.0.0 --port 8443 --ssl-keyfile "$KATUP_STATE/tls.key" --ssl-certfile "$KATUP_STATE/tls.crt" --no-access-log ;;
 simulation) exec unshare --user --map-root-user --net "$KATUP_REPO/deploy/simulation-net.sh" ;;
 *) exit 2 ;;
esac
