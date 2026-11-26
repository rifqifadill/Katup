from pathlib import Path
import re


log = Path(__file__).resolve().parents[1] / '.runtime-llm/public-tunnel.log'
urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', log.read_text() if log.exists() else '')
if not urls:
    raise SystemExit('URL belum siap, cek sudo journalctl -u katup-llm-tunnel -n 30 --no-pager')
print(urls[-1])
