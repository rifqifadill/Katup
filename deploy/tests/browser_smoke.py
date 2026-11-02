import argparse,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
RUNTIME=Path(__file__).resolve().parents[3]/'runtime'
creds=json.loads((RUNTIME/'state/credentials.json').read_text())
parser=argparse.ArgumentParser()
parser.add_argument('--url',default='https://127.0.0.1:8443')
parser.add_argument('--allow-self-signed',action='store_true')
args=parser.parse_args()
results={'url':args.url,'browser_certificate_validation':not args.allow_self_signed}
def login(page):
 page.goto(args.url.rstrip('/')+'/')
 page.locator('[name=username]').fill(creds['username'])
 page.locator('[name=password]').fill(creds['password'])
 page.locator('button').click()
 page.wait_for_function("document.querySelector('#connection')?.textContent.includes('Desktop terhubung')",timeout=25000)

def state(page): return page.evaluate("fetch('/api/status').then(r=>r.json())")
def wait_state(page, predicate, timeout=120):
 end=time.time()+timeout
 while time.time()<end:
  s=state(page)
  if predicate(s): return s
  page.wait_for_timeout(500)
 raise AssertionError(s)

with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 ctx=b.new_context(ignore_https_errors=args.allow_self_signed,viewport={'width':1400,'height':1050})
 page=ctx.new_page()
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 login(page)
 results['login_and_novnc']=True
 for mode in ('baseline','katup'):
  page.select_option('#mode',mode)
  page.click('#start')
  s=wait_state(page,lambda s:s['running'] and s['telemetry'].get('scenario')==mode and s['telemetry'].get('simulation_time',0)>10)
  a=s['telemetry']
  page.wait_for_timeout(300)
  z=state(page)['telemetry']
  assert z['simulation_time']>a['simulation_time']
  assert a['sample_vehicle']==z['sample_vehicle'] and a['sample_position']!=z['sample_position'],(a,z)
  if mode=='baseline':
   assert z['calls']['pengamat']>0 and z['calls']['katup']==z['calls']['rute']==0
   assert z['control']['rerouted']==0
  else:
   z=wait_state(page,lambda s:s['telemetry'].get('control',{}).get('rerouted',0)>0)['telemetry']
   assert all(z['calls'][k]>0 for k in ('pengamat','katup','rute'))
  results[mode]=z
  page.screenshot(path=str(RUNTIME/f'verified-{mode}.png'))
 page.click('#stop')
 s=wait_state(page,lambda s:not s['running'])
 results['stop']=True
 page.select_option('#mode','katup')
 page.click('#start')
 wait_state(page,lambda s:s['running'] and s['telemetry'].get('simulation_time',0)>5)
 results['restart_after_stop']=True
 mobile=b.new_context(ignore_https_errors=args.allow_self_signed,viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=1)
 mp=mobile.new_page()
 login(mp)
 assert mp.locator('#start').is_visible()
 mp.screenshot(path=str(RUNTIME/'verified-mobile.png'))
 results['mobile_view_and_novnc']=True
 results['javascript_errors']=errors
 b.close()
(RUNTIME/'verification.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
