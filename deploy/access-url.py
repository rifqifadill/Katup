"""Print this running tunnel's URL; never return a previous invocation's URL."""
import os,re,subprocess,sys
os.environ['XDG_RUNTIME_DIR']='/run/user/'+str(os.getuid())
invocation=subprocess.check_output(['systemctl','--user','show','katup-tunnel','--property=InvocationID','--value'],text=True).strip()
if not invocation: sys.exit('Tunnel is not running.')
logs=subprocess.check_output(['journalctl','--user',f'_SYSTEMD_INVOCATION_ID={invocation}','--no-pager','-o','cat'],text=True)
urls=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',logs)
if not urls: sys.exit('Tunnel URL is not ready; inspect journalctl --user -u katup-tunnel -n 30')
print(urls[-1])
