"""Install the headless public demo on Ubuntu, preserving other web services.

Run with the application user's Python, not with sudo. SUMO and python3-venv
must already be installed. Only systemd registration invokes sudo.
"""
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import urllib.request

repo = Path(__file__).resolve().parents[1]
runtime = repo.parent / 'runtime'
state = runtime / 'state'
for directory in (state, runtime / 'novnc', runtime / 'bin'):
    directory.mkdir(parents=True, exist_ok=True)
state.chmod(0o700)
credentials = state / 'credentials.json'
if not credentials.exists():
    credentials.write_text(json.dumps(dict(username='katup', password=secrets.token_urlsafe(24), desktop_password=secrets.token_urlsafe(24))))
    credentials.chmod(0o600)
venv = runtime / 'venv'
if not (venv / 'bin/python').exists():
    subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
subprocess.run([str(venv / 'bin/pip'), 'install', '-r', str(repo / 'deploy/public-requirements.txt')], check=True)
version = '2026.10.7'
expected = '1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872'
binary = runtime / 'bin/cloudflared'
if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
    data = urllib.request.urlopen(f'https://github.com/cloudflare/cloudflared/releases/download/{version}/cloudflared-linux-amd64', timeout=90).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Cloudflared checksum mismatch')
    binary.write_bytes(data)
    binary.chmod(0o755)
user = subprocess.check_output(['id', '-un'], text=True).strip()
common = f'''User={user}
Restart=always
RestartSec=3
NoNewPrivileges=true
'''
units = {
    'katup-dashboard': f'''[Unit]
Description=KATUP public headless dashboard
After=network-online.target
Wants=network-online.target
[Service]
{common}WorkingDirectory={repo}
Environment=KATUP_PUBLIC_MODE=1
Environment=KATUP_STANDALONE=1
Environment=KATUP_STATE={state}
Environment=KATUP_NOVNC={runtime / 'novnc'}
Environment=SUMO_HOME=/usr/share/sumo
Environment=PYTHONUNBUFFERED=1
ExecStart={venv / 'bin/uvicorn'} deploy.server:app --host 127.0.0.1 --port 9000 --no-access-log
[Install]
WantedBy=multi-user.target
''',
    'katup-tunnel': f'''[Unit]
Description=KATUP public HTTPS tunnel
After=katup-dashboard.service network-online.target
Wants=katup-dashboard.service
[Service]
{common}ExecStart={binary} tunnel --url http://127.0.0.1:9000 --no-autoupdate --loglevel info
[Install]
WantedBy=multi-user.target
''',
}
for name, content in units.items():
    subprocess.run(['sudo', 'tee', f'/etc/systemd/system/{name}.service'], input=content, text=True, check=True, stdout=subprocess.DEVNULL)
subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
subprocess.run(['sudo', 'systemctl', 'enable', '--now', 'katup-dashboard', 'katup-tunnel'], check=True)
print('Installed. Read the current HTTPS URL with: python3 deploy/public-url.py')
