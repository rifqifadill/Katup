"""Register isolated user services; no root and no edits to other services."""
from pathlib import Path
import json,os,secrets,socket,struct,subprocess
repo=Path(__file__).resolve().parents[1]
state=repo.parent/'runtime/state'
# Xauthority record: local hostname, display, protocol, cookie.
def field(value): return struct.pack('!H',len(value))+value
cookie=secrets.token_bytes(16)
auth=state/'Xauthority'
if not auth.exists():
    auth.write_bytes(struct.pack('!H',256)+field(socket.gethostname().encode())+field(b'95')+field(b'MIT-MAGIC-COOKIE-1')+field(cookie))
auth.chmod(0o600)
credentials=json.loads((state/'credentials.json').read_text())
env=os.environ.copy()
env['LD_LIBRARY_PATH']=str(repo.parent/'runtime/root/usr/lib/x86_64-linux-gnu')+':'+str(repo.parent/'runtime/root/lib/x86_64-linux-gnu')
subprocess.run([str(repo.parent/'runtime/root/usr/bin/x11vnc'),'-storepasswd',credentials['desktop_password'],str(state/'vnc.pass')],env=env,check=True)
units=Path.home()/'.config/systemd/user'
units.mkdir(parents=True,exist_ok=True)
for name,cmd,requires in [('display','display',[]),('desktop','desktop',['display']),('vnc','vnc',['display']),('web','web',['vnc','desktop']),('simulation','simulation',['vnc','desktop'])]:
    dependencies=' '.join('katup-'+r+'.service' for r in requires)
    unit=f'''[Unit]
Description=KATUP {name}
'''
    if requires: unit+=f'Requires={dependencies}\nAfter={dependencies}\n'
    unit+=f'''
[Service]
Type=simple
ExecStart="{repo}/deploy/service.sh" {cmd}
Restart={'no' if name=='simulation' else 'on-failure'}
RestartSec=3
KillMode=control-group
TimeoutStopSec=12
UMask=0077
NoNewPrivileges=true
'''
    if name not in ('display','web'): unit+='ExecStartPre=/bin/sleep 1\n'
    if name!='simulation': unit+='\n[Install]\nWantedBy=default.target\n'
    (units/f'katup-{name}.service').write_text(unit)
print('Units written to', units)
