import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT=Path(__file__).resolve().parents[1]
STATE=Path(os.environ['KATUP_STATE'])
AUTH=json.loads((STATE/'credentials.json').read_text())
sessions=set()
attempts={}
lock=asyncio.Lock()
proc=None
scenario=None

def authorized(request):
    return request.cookies.get('katup_session') in sessions


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def comparison_data():
    runs = STATE / 'runs'
    return {
        mode: read_json(runs / f'{mode}.json', {})
        for mode in ('baseline', 'katup')
    }


def origin_allowed(ws):
    origin = ws.headers.get('origin', '')
    host = ws.headers.get('host', '')
    return origin in {f'https://{host}', f'http://{host}'}

async def stop():
    global proc, scenario
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
    running=(await asyncio.to_thread(subprocess.run,['systemctl','--user','is-active','--quiet','katup-simulation.service'])).returncode==0
    data=read_json(STATE/'telemetry.json')
    return {'running':running,'telemetry':data,'comparison':comparison_data()}


@app.get('/api/comparison')
async def comparison():
    return comparison_data()

@app.post('/api/start/{mode}')
async def start(mode:str, delay_ms:int=1000):
    if delay_ms not in (100,200,1000): return JSONResponse({'error':'Kecepatan tidak dikenal'},400)
    if mode not in ('baseline','katup'): return JSONResponse({'error':'Skenario tidak dikenal'},400)
    async with lock:
        await stop()
        (STATE/'scenario').write_text(mode)
        (STATE/'delay-ms').write_text(str(delay_ms))
        (STATE/'telemetry.json').unlink(missing_ok=True)
        result=await asyncio.to_thread(subprocess.run,['systemctl','--user','start','katup-simulation.service'])
        if result.returncode: return JSONResponse({'error':'Gagal memulai layanan'},500)
    return {'started':mode}

@app.post('/api/stop')
async def stop_api():
    async with lock: await stop()
    return {'stopped':True}

@app.get('/api/desktop')
async def desktop(): return {'password':AUTH['desktop_password']}


@app.websocket('/api/stream')
async def telemetry_stream(ws:WebSocket):
    if not authorized(ws) or not origin_allowed(ws):
        await ws.close(code=1008)
        return
    await ws.accept()
    last_signature = None
    try:
        while True:
            data = read_json(STATE/'telemetry.json')
            signature = (data.get('updated'), data.get('step'), data.get('finished'))
            if signature != last_signature:
                await ws.send_json({'telemetry': data, 'comparison': comparison_data()})
                last_signature = signature
            await asyncio.sleep(0.5)
    except Exception:
        return

@app.websocket('/websockify')
async def proxy(ws:WebSocket):
    if not authorized(ws) or not origin_allowed(ws):
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
