"""Optional trusted HTTPS access without inbound port changes or a domain."""
import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request

repo=Path(__file__).resolve().parents[1]
runtime=repo.parent/'runtime'
version='2026.10.7'
expected='1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872'
binary=runtime/'bin/cloudflared'
binary.parent.mkdir(parents=True,exist_ok=True)
if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest()!=expected:
    data=urllib.request.urlopen(f'https://github.com/cloudflare/cloudflared/releases/download/{version}/cloudflared-linux-amd64',timeout=60).read()
    if hashlib.sha256(data).hexdigest()!=expected: raise RuntimeError('cloudflared checksum mismatch')
    binary.write_bytes(data)
    binary.chmod(0o755)
unit=Path.home()/'.config/systemd/user/katup-tunnel.service'
unit.write_text(f'''[Unit]
Description=KATUP trusted HTTPS quick tunnel
Wants=katup-web.service
After=katup-web.service network-online.target
[Service]
ExecStart="{repo}/deploy/tunnel.sh"
Restart=always
RestartSec=10
UMask=0077
NoNewPrivileges=true
[Install]
WantedBy=default.target
''')
env=os.environ.copy()
env['XDG_RUNTIME_DIR']='/run/user/'+str(os.getuid())
subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
subprocess.run(['systemctl','--user','enable','--now','katup-tunnel'],env=env,check=True)
print('Use python deploy/access-url.py to read the current public HTTPS URL.')
