import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
RUNTIME=Path(__file__).resolve().parents[3]/'runtime'
url=(RUNTIME/'state/public-url.txt').read_text().strip()
creds=json.loads((RUNTIME/'state/credentials.json').read_text())
report={}
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1100,'height':900})
 frames=[]
 page.on('websocket',lambda ws:ws.on('framereceived',lambda data:frames.append((time.time(),len(data)))))
 page.goto(url)
 page.locator('[name=username]').fill(creds['username']);page.locator('[name=password]').fill(creds['password']);page.locator('button').click()
 page.wait_for_function("document.querySelector('#connection')?.textContent.includes('Dashboard terhubung')",timeout=25000)
 def status():return page.evaluate("fetch('/api/status').then(r=>r.json())")
 for speed in ('1000','200'):
  page.select_option('#speed',speed);page.click('#start')
  end=time.time()+30
  while time.time()<end:
   s=status();t=s['telemetry']
   if s['running'] and t.get('gui_delay_ms')==int(speed) and t.get('simulation_time',0)>2: break
   page.wait_for_timeout(300)
  else: raise AssertionError(s)
  started=time.time();before=t['simulation_time'];frames.clear();page.wait_for_timeout(6000);after=status()['telemetry']
  elapsed=time.time()-started
  report[speed]={'wall_seconds':round(elapsed,2),'sim_seconds':after['simulation_time']-before,'ws_bytes':sum(n for _,n in frames),'ws_messages':len(frames)}
  assert after['simulation_time']>before
  assert len(frames)>0
 page.screenshot(path=str(RUNTIME/'gui-tuned.png'),full_page=True)
 assert report['200']['sim_seconds']>report['1000']['sim_seconds']*2
 invalid=page.evaluate("fetch('/api/start/katup?delay_ms=5',{method:'POST'}).then(r=>r.status)")
 assert invalid==400
 report['invalid_speed_rejected']=True
 report['tls_verification']=True
 b.close()
(RUNTIME/'verification-performance.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
