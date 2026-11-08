import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from functools import lru_cache
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from katup_scenario import CASE_DIR, build_scenario, case_metadata

ROOT=Path(__file__).resolve().parents[1]
STATE=Path(os.environ['KATUP_STATE'])
AUTH=json.loads((STATE/'credentials.json').read_text())
PUBLIC_MODE=os.environ.get('KATUP_PUBLIC_MODE','0') == '1'
STANDALONE=os.environ.get('KATUP_STANDALONE','0') == '1'
sessions=set()
attempts={}
lock=asyncio.Lock()
proc=None
proc_log=None
scenario=None
build_scenario()
CASE = case_metadata()

def authorized(request):
    return PUBLIC_MODE or request.cookies.get('katup_session') in sessions


@lru_cache(maxsize=8)
def cached_json(path, modified):
    return json.loads(path.read_text())


def read_json(path, default=None):
    try:
        return dict(cached_json(path, path.stat().st_mtime_ns))
    except (OSError, ValueError):
        return {} if default is None else default


def comparison_data():
    runs = STATE / 'runs'
    result = {}
    for mode in ('baseline', 'katup'):
        run = read_json(runs / f'{mode}.json', {})
        result[mode] = run if run.get('case', {}).get('signature') == CASE['signature'] else {}
    return result


async def simulation_running():
    if STANDALONE:
        return proc is not None and proc.poll() is None
    return (await asyncio.to_thread(subprocess.run, ['systemctl','--user','is-active','--quiet','katup-simulation.service'])).returncode == 0


def origin_allowed(ws):
    origin = ws.headers.get('origin', '')
    host = ws.headers.get('host', '')
    return origin in {f'https://{host}', f'http://{host}'}

async def stop():
    global proc, proc_log, scenario
    if STANDALONE:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                await asyncio.to_thread(proc.wait, 12)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
        if proc_log is not None:
            proc_log.close()
            proc_log = None
    else:
        # systemd kills all processes in this separate simulation cgroup, including SUMO.
        await asyncio.to_thread(subprocess.run, ['systemctl','--user','stop','katup-simulation.service'], check=False)
    proc=None
    scenario=None

@asynccontextmanager
async def lifespan(app):
    yield
    await stop()

app=FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware('http')
async def authenticate(request, call_next):
    if request.url.path != '/login' and not authorized(request):
        return RedirectResponse('/login', status_code=303)
    if request.method == 'POST' and request.url.path != '/login':
        if request.headers.get('origin') != str(request.base_url).rstrip('/'):
            return JSONResponse({'error':'Origin tidak diizinkan'}, status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.get('/login')
async def login_page():
    return HTMLResponse('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Masuk · KATUP</title><style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 75% 0,#16445a,#07131f 55%);color:#eaf6f4;font:16px system-ui;padding:20px}.box{width:min(420px,100%);padding:30px;border:1px solid #214052;border-radius:22px;background:rgba(14,33,48,.94);box-shadow:0 24px 80px #0006}.logo{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(135deg,#55e6c1,#2ba6c5);color:#05202a;font-size:22px;font-weight:900;margin-bottom:20px}h1{margin:0;font-size:27px}p{color:#8fa9b2;margin:8px 0 24px}label{display:block;font-size:12px;color:#b8d3d4;margin:14px 0 6px}input,button{display:block;width:100%;padding:13px;border-radius:12px;font:inherit}input{border:1px solid #315268;background:#091b29;color:#eaf6f4}button{margin-top:20px;border:0;background:#55e6c1;color:#05202a;font-weight:800;cursor:pointer}</style><main class="box"><div class="logo">K</div><h1>KATUP Traffic Control</h1><p>Dashboard simulasi antrean dan pengaturan rute berbasis SUMO + TraCI.</p><form method="post"><label>Nama pengguna</label><input name="username" autocomplete="username" required><label>Kata sandi</label><input name="password" type="password" autocomplete="current-password" required><button>Masuk ke dashboard</button></form></main>''')

@app.post('/login')
async def login(request:Request):
    from urllib.parse import parse_qs
    ip=request.client.host
    now=time.time()
    recent=[t for t in attempts.get(ip,[]) if now-t<60]
    if len(recent)>=10: return HTMLResponse('Coba lagi setelah satu menit.',429)
    fields=parse_qs((await request.body()).decode())
    good=hmac.compare_digest(fields.get('username',[''])[0],AUTH['username']) and hmac.compare_digest(fields.get('password',[''])[0],AUTH['password'])
    if not good:
        attempts[ip]=recent+[now]
        return HTMLResponse('Login gagal. <a href="/login">Kembali</a>',401)
    token=secrets.token_urlsafe(32)
    sessions.add(token)
    response=RedirectResponse('/',303)
    response.set_cookie('katup_session',token,secure=True,httponly=True,samesite='strict')
    return response

@app.get('/')
async def index(): return HTMLResponse((ROOT/'deploy/index.html').read_text())

@app.get('/api/status')
async def status():
    running=await simulation_running()
    data=read_json(STATE/'telemetry.json')
    data.pop('traceback', None)
    if data.get('case', {}).get('signature') != CASE['signature']:
        data = {}
    return {'running':running,'public_mode':PUBLIC_MODE,'case':CASE,'telemetry':data,'comparison':comparison_data()}


@app.get('/api/comparison')
async def comparison():
    return comparison_data()


@lru_cache(maxsize=1)
def network_data():
    root = ET.parse(CASE_DIR/'network.net.xml').getroot()
    def points(shape):
        return [[float(v) for v in pair.split(',')] for pair in shape.split()]
    edges = []
    for edge in root.findall('edge'):
        edges.append({'id': edge.get('id'), 'internal': edge.get('function') == 'internal',
                      'lanes': [{'shape': points(lane.get('shape')), 'width': float(lane.get('width', '3.2'))}
                                for lane in edge.findall('lane')]})
    junctions = [{'id': j.get('id'), 'shape': points(j.get('shape'))}
                 for j in root.findall('junction') if j.get('type') != 'internal' and j.get('shape')]
    return {'edges': edges, 'junctions': junctions, 'case': CASE}


@app.get('/api/network')
async def network():
    return network_data()

@app.post('/api/start/{mode}')
async def start(mode:str, delay_ms:int=1000):
    global proc, proc_log, scenario
    if delay_ms not in (100,200,1000): return JSONResponse({'error':'Kecepatan tidak dikenal'},400)
    if mode not in ('baseline','katup'): return JSONResponse({'error':'Skenario tidak dikenal'},400)
    async with lock:
        await stop()
        (STATE/'scenario').write_text(mode)
        (STATE/'delay-ms').write_text(str(delay_ms))
        (STATE/'telemetry.json').unlink(missing_ok=True)
        if STANDALONE:
            env=os.environ.copy()
            env.update({
                'KATUP_STATE':str(STATE),
                'KATUP_TELEMETRY':str(STATE/'telemetry.json'),
                'KATUP_SCENARIO':mode,
                'KATUP_DELAY':str(delay_ms),
                'KATUP_USE_GUI':'0',
                'SUMO_HOME':env.get('SUMO_HOME','/usr/share/sumo'),
                'PYTHONUNBUFFERED':'1',
            })
            proc_log=open(STATE/'simulation.log','a',encoding='utf-8')
            proc=subprocess.Popen(
                [sys.executable,str(ROOT/'deploy/run_controller.py'),mode],
                cwd=ROOT,env=env,stdout=proc_log,stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            scenario=mode
        else:
            result=await asyncio.to_thread(subprocess.run,['systemctl','--user','start','katup-simulation.service'])
            if result.returncode: return JSONResponse({'error':'Gagal memulai layanan'},500)
    return {'started':mode}

@app.post('/api/stop')
async def stop_api():
    async with lock: await stop()
    return {'stopped':True}

@app.get('/api/desktop')
async def desktop():
    if PUBLIC_MODE: return JSONResponse({'error':'SUMO-GUI detail dinonaktifkan pada mode publik'},403)
    return {'password':AUTH['desktop_password']}


@app.websocket('/api/stream')
async def telemetry_stream(ws:WebSocket):
    if not authorized(ws) or not origin_allowed(ws):
        await ws.close(code=1008)
        return
    await ws.accept()
    last_signature = None
    last_series = None
    last_comparison = None
    disconnected = asyncio.create_task(ws.receive())
    try:
        while not disconnected.done():
            data = read_json(STATE/'telemetry.json')
            if data.get('case', {}).get('signature') != CASE['signature']:
                data = {}
            data.pop('traceback', None)
            data['running'] = await simulation_running()
            data['public_mode'] = PUBLIC_MODE
            signature = (data.get('updated'), data.get('step'), data.get('finished'), data['running'])
            if signature != last_signature:
                history = data.get('series', [])
                series_signature = (data.get('run_id'), history[-1].get('time') if history else None)
                if series_signature == last_series:
                    data.pop('series', None)
                last_series = series_signature
                revision = tuple((STATE/'runs'/f'{mode}.json').stat().st_mtime_ns if (STATE/'runs'/f'{mode}.json').exists() else 0 for mode in ('baseline','katup'))
                payload = {'telemetry': data, 'case': CASE}
                if revision != last_comparison:
                    payload['comparison'] = comparison_data()
                    last_comparison = revision
                await ws.send_json(payload)
                last_signature = signature
            await asyncio.wait([disconnected], timeout=0.1)
    except Exception:
        return
    finally:
        disconnected.cancel()
        await asyncio.gather(disconnected, return_exceptions=True)

@app.websocket('/websockify')
async def proxy(ws:WebSocket):
    if PUBLIC_MODE or not authorized(ws) or not origin_allowed(ws):
        await ws.close(code=1008)
        return
    await ws.accept(subprotocol='binary' if 'binary' in ws.headers.get('sec-websocket-protocol','') else None)
    reader,writer=await asyncio.open_connection('127.0.0.1',5905)
    async def tcp_to_ws():
        while data:=await reader.read(65536): await ws.send_bytes(data)
    async def ws_to_tcp():
        while True:
            writer.write(await ws.receive_bytes())
            await writer.drain()
    tasks=[asyncio.create_task(tcp_to_ws()),asyncio.create_task(ws_to_tcp())]
    try: await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        writer.close()
        await writer.wait_closed()

app.mount('/novnc',StaticFiles(directory=os.environ['KATUP_NOVNC']),name='novnc')
app.mount('/assets',StaticFiles(directory=ROOT/'deploy/assets'),name='assets')
