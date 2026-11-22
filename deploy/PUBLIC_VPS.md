# Public KATUP on the new VPS

The new Ubuntu VPS has public egress IP `43.134.46.245`. The dashboard runs on
`127.0.0.1:9000`; Cloudflare Tunnel publishes it with trusted HTTPS. No inbound
port needs to be opened. Port 8443 belongs to another application and is unchanged.
The older host addresses and noVNC installation in `deploy/README.md` describe
an earlier VPS, not this installation.

The public dashboard has no login. All visitors share one simulation and may
start/change/stop that session. It runs SUMO headless. Raw VNC/WebSocket desktop
access and the desktop password endpoint are disabled in public mode.

## Installation

Requires Ubuntu, `sumo`, `python3-venv`, and permission to register system services.
Run as the application user:

```bash
python3 deploy/install-public.py
python3 deploy/public-url.py
```

The installer creates `../runtime/venv`, private runtime state, and two system
services: `katup-dashboard` and `katup-tunnel`. It enables both at boot and
verifies the downloaded cloudflared binary against a pinned SHA-256.

For source updates, update the checkout and restart **only** the dashboard:

```bash
sudo systemctl restart katup-dashboard
```

The installer preserves an already-running tunnel. A dashboard restart should
not change the URL. Restarting the tunnel or rebooting the VPS may change the
Quick Tunnel hostname. Read the current invocation's URL with:

```bash
python3 deploy/public-url.py
sudo systemctl status katup-dashboard katup-tunnel
journalctl -u katup-dashboard -n 30
```

Quick Tunnels have no uptime guarantee. For a permanent URL, configure a named
Cloudflare tunnel and a domain belonging to the group.

## Verification

Run the public browser smoke test with trusted certificate validation enabled:

```bash
python3 deploy/tests/public_smoke.py --url "$(python3 deploy/public-url.py)"
```

It starts/stops the shared simulation, checks real vehicle movement and telemetry
WebSocket messages, checks mobile overflow, and verifies that public desktop
access is disabled. The test requires Playwright and Chromium.

Completed comparison data is in `../runtime/state/runs/baseline.json` and
`katup.json`. Both must be full runs of the same seed before comparing results.
Metrics describe completed trips; vehicles still running or waiting to enter at
1800 seconds are not included in those averages. SUMO 1.18 uses the documented
elapsed-phase fallback. No controller thresholds were tuned for the website.
