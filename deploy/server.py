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
    return HTMLResponse('''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login KATUP</title><style>body{font:18px system-ui;max-width:380px;margin:10vh auto;padding:20px;background:#102131;color:white}input,button{display:block;padding:12px;margin:12px 0;width:90%}</style><h1>KATUP</h1><form method="post"><input name="username" placeholder="Nama pengguna" autocomplete="username" required><input name="password" type="password" placeholder="Kata sandi" autocomplete="current-password" required><button>Masuk</button></form>''')

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
    data={}
    try: data=json.loads((STATE/'telemetry.json').read_text())
    except (OSError,ValueError): pass
    return {'running':running,'telemetry':data}

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

@app.websocket('/websockify')
async def proxy(ws:WebSocket):
    if not authorized(ws) or ws.headers.get('origin') != 'https://'+ws.headers.get('host',''):
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
