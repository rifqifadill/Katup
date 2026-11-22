"""Ubuntu 22.04 user-local runtime, without apt install or sudo."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import urllib.request

repo=Path(__file__).resolve().parents[1]
runtime=repo.parent/'runtime'
root=runtime/'root'
state=runtime/'state'
for path in (runtime/'debs',root,state): path.mkdir(parents=True,exist_ok=True)
state.chmod(0o700)
packages=['xvfb','x11vnc','openbox','mesa-utils','libgl1-mesa-dri','libatomic1','fonts-dejavu-core']
plan=subprocess.check_output(['apt-get','-s','install','--no-install-recommends',*packages],text=True)
missing=[line.split()[1] for line in plan.splitlines() if line.startswith('Inst ')]
# Include requested packages even when the host already has them.
uris=subprocess.check_output(['apt-get','download','--print-uris',*sorted(set(packages+missing))],text=True)
(runtime/'apt-uris.txt').write_text(uris)

def fetch(line):
    parts=shlex.split(line)
    if len(parts)<4: return
    url,name,size,digest=parts[:4]
    url=url.replace('http://id.archive.ubuntu.com','https://archive.ubuntu.com').replace('http://security.ubuntu.com','https://security.ubuntu.com')
    path=runtime/'debs'/name
    algo,expected=digest.split(':')
    def valid(data): return hashlib.new(algo.lower(),data).hexdigest()==expected
    if path.exists() and valid(path.read_bytes()): return path
    for attempt in range(3):
        try:
            data=urllib.request.urlopen(url,timeout=60).read()
            if not valid(data): raise ValueError('Checksum mismatch: '+name)
            path.write_bytes(data)
            return path
        except Exception:
            if attempt==2: raise
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    downloads=list(pool.map(fetch,uris.splitlines()))
for deb in downloads:
    if deb: subprocess.run(['dpkg-deb','-x',str(deb),str(root)],check=True)
# Localize Xvfb's compiled xkbcomp directory. Only this private binary is patched.
original=(root/'usr/bin/Xvfb').read_bytes()
if original.count(b'/usr/bin\0')!=1: raise RuntimeError('Unsupported Xvfb binary; inspect xkbcomp path')
local=root/'usr/bin/Xvfb-local'
local.write_bytes(original.replace(b'/usr/bin\0',b'.\0'+b'\0'*7))
local.chmod(0o755)
venv=runtime/'venv'
if not (venv/'bin/python').exists():
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(venv)],check=True)
    installer=runtime/'get-pip.py'
    installer.write_bytes(urllib.request.urlopen('https://bootstrap.pypa.io/get-pip.py').read())
    subprocess.run([str(venv/'bin/python'),str(installer)],check=True)
subprocess.run([str(venv/'bin/pip'),'install','-r',str(repo/'deploy/requirements.lock.txt')],check=True)
novnc=runtime/'novnc'
if not novnc.exists():
    subprocess.run(['git','clone','https://github.com/novnc/noVNC.git',str(novnc)],check=True)
    subprocess.run(['git','-C',str(novnc),'checkout',(repo/'deploy/novnc-revision.txt').read_text().strip()],check=True)
credentials=state/'credentials.json'
if not credentials.exists():
    credentials.write_text(json.dumps(dict(username='katup',password=secrets.token_urlsafe(18),desktop_password=secrets.token_hex(4))))
    credentials.chmod(0o600)
(state/'fonts.conf').write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>{root}/usr/share/fonts</dir><cachedir>{state}/font-cache</cachedir></fontconfig>')
if not (state/'tls.key').exists():
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','365','-keyout',str(state/'tls.key'),'-out',str(state/'tls.crt'),'-subj','/CN=KATUP','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost'],check=True)
    (state/'tls.key').chmod(0o600)
subprocess.run(['loginctl','enable-linger',os.environ['USER']],check=True)
subprocess.run([sys.executable,str(repo/'deploy/install-services.py')],check=True)
env=os.environ.copy()
env['XDG_RUNTIME_DIR']='/run/user/'+str(os.getuid())
subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
subprocess.run(['systemctl','--user','enable','--now','katup-display','katup-desktop','katup-vnc','katup-web'],env=env,check=True)
print('Ready: https://127.0.0.1:8443; credentials:',credentials)
