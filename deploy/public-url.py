"""Print the URL from the current system tunnel invocation only."""
import re
import subprocess

invocation = subprocess.check_output(['systemctl', 'show', 'katup-tunnel.service', '-p', 'InvocationID', '--value'], text=True).strip()
if not invocation:
    raise SystemExit('Tunnel is not running')
logs = subprocess.check_output(['journalctl', f'_SYSTEMD_INVOCATION_ID={invocation}', '--no-pager'], text=True)
urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', logs)
if not urls:
    raise SystemExit('URL not ready; inspect journalctl -u katup-tunnel')
print(urls[-1])
