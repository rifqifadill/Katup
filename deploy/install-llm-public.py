import os
from pathlib import Path
import pwd
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime-llm'
PYTHON = ROOT / '.venv/bin/python'
CLOUDFLARED = Path(shutil.which('cloudflared') or ROOT.parent / 'runtime/bin/cloudflared')
USER = pwd.getpwuid(os.getuid()).pw_name


def install():
    if os.getuid() == 0:
        raise SystemExit('jalankan memakai akun pemilik project, tanpa sudo di depan python')
    if not PYTHON.exists() or not CLOUDFLARED.exists():
        raise SystemExit('siapkan virtualenv project dan cloudflared terlebih dulu')
    STATE.mkdir(parents=True, exist_ok=True)
    units = {
        'katup-llm-dashboard': f'''[Unit]
Description=KATUP LLM public demo, API disabled
After=network-online.target
Wants=network-online.target

[Service]
User={USER}
WorkingDirectory={ROOT}
Environment=KATUP_PUBLIC_MODE=1
Environment=KATUP_STANDALONE=1
Environment=KATUP_STATE={STATE}
Environment=KATUP_CORRIDOR=ui_depok
Environment=KATUP_LLM_PROVIDER=disabled
Environment=KATUP_LLM_API_KEY=
Environment=KATUP_FRONTEND_ORIGINS=
Environment=SUMO_HOME=/usr/share/sumo
Environment=PYTHONUNBUFFERED=1
ExecStart={PYTHON} -m uvicorn deploy.server:app --host 127.0.0.1 --port 19010 --no-access-log
Restart=always
RestartSec=3
TimeoutStopSec=20
KillMode=control-group
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
''',
        'katup-llm-tunnel': f'''[Unit]
Description=KATUP LLM public HTTPS quick tunnel
After=network-online.target katup-llm-dashboard.service
Wants=network-online.target katup-llm-dashboard.service

[Service]
User={USER}
WorkingDirectory={ROOT}
ExecStartPre=/usr/bin/truncate --size=0 {STATE}/public-tunnel.log
ExecStart={CLOUDFLARED} tunnel --url http://127.0.0.1:19010 --no-autoupdate --protocol http2 --metrics 127.0.0.1:20242 --loglevel info --logfile {STATE}/public-tunnel.log
Restart=always
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
''',
    }
    for name, content in units.items():
        subprocess.run(['sudo', '-n', 'tee', f'/etc/systemd/system/{name}.service'], input=content, text=True, stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['sudo', '-n', 'systemctl', 'daemon-reload'], check=True)
    subprocess.run(['sudo', '-n', 'systemctl', 'enable', *units], check=True)
    subprocess.run(['sudo', '-n', 'systemctl', 'restart', *units], check=True)
    print('demo publik terpasang, baca URL memakai python3 deploy/llm-public-url.py')


if __name__ == '__main__':
    install()
