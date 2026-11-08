"""Public HTTPS end-to-end check; intentionally controls the shared session."""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--output', default='/tmp/katup-public-verification.json')
args = parser.parse_args()
url = args.url.rstrip('/')
report = {'url': url, 'certificate_validation': True}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    frames = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.on('websocket', lambda ws: ws.on('framereceived', lambda data: frames.append(len(data))))
    response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
    assert response.status == 200
    assert page.locator('[name=username]').count() == 0
    report['no_login'] = True
    page.select_option('#mode', 'katup')
    page.select_option('#speed', '100')
    page.click('#start')
    deadline = time.time() + 40
    previous = {}
    while time.time() < deadline:
        snapshot = page.evaluate("fetch('/api/status').then(r=>r.json())")
        telemetry = snapshot.get('telemetry', {})
        if snapshot['running'] and telemetry.get('scenario') == 'katup' and telemetry.get('simulation_time', 0) >= 5:
            previous = telemetry
            break
        page.wait_for_timeout(500)
    assert previous
    page.wait_for_timeout(3000)
    current = page.evaluate("fetch('/api/status').then(r=>r.json()).then(s=>s.telemetry)")
    assert current['simulation_time'] > previous['simulation_time']
    a = {v['id']: (v['x'], v['y']) for v in previous['vehicles_sample']}
    b = {v['id']: (v['x'], v['y']) for v in current['vehicles_sample']}
    assert any(a[key] != b[key] for key in a.keys() & b.keys())
    assert frames, 'No telemetry WebSocket frames received'
    report.update(vehicle_movement=True, websocket_frames=len(frames))
    assert page.evaluate("fetch('/api/desktop').then(r=>r.status)") == 403
    report['desktop_disabled'] = True
    page.set_viewport_size({'width': 390, 'height': 844})
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    report['mobile_no_overflow'] = True
    page.click('#stop')
    page.wait_for_timeout(1000)
    assert not page.evaluate("fetch('/api/status').then(r=>r.json()).then(s=>s.running)")
    report['stop'] = True
    report['page_errors'] = errors
    assert not errors
    browser.close()
Path(args.output).write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
