import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = os.getenv('KATUP_TEST_URL', 'http://127.0.0.1:19010').rstrip('/')
OUTPUT = Path(os.getenv('KATUP_BROWSER_OUTPUT', 'output/browser'))


def verify():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    errors = []
    evidence = {'base': BASE, 'modes': [], 'screens': [], 'console_errors': errors}
    with sync_playwright() as playwright:
        executable = os.getenv('KATUP_CHROMIUM')
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE, wait_until='networkidle')
        config = page.evaluate("fetch('/api/catalog').then(r=>r.json())")
        assert not config['llm']['configured'], 'pengujian ini harus memakai API nonaktif'
        page.wait_for_function("document.querySelector('#corridor').options.length>=6 && document.querySelectorAll('#roads polyline').length>30")
        assert page.locator('#queueChart,#speedChart,.agent-card,.decision-panel,.events').count() == 0
        for mode in ('baseline', 'katup', 'hybrid'):
            page.select_option('#mode', mode)
            page.select_option('#speed', '100')
            page.click('#start')
            page.wait_for_function("state.telemetry.running && state.telemetry.step>=10")
            first = page.evaluate('state.telemetry')
            page.wait_for_function('(step)=>state.telemetry.step>step+5', arg=first['step'])
            second = page.evaluate('state.telemetry')
            assert page.input_value('#mode') == mode
            assert page.is_disabled('#start') and page.is_disabled('#corridor')
            assert not page.is_visible('#comparison')
            assert second['simulation_time'] > first['simulation_time']
            before = {v['id']: (v['x'], v['y']) for v in first['vehicles_sample']}
            moved = sum(before[v['id']] != (v['x'], v['y']) for v in second['vehicles_sample'] if v['id'] in before)
            assert moved > 0
            if mode == 'hybrid':
                assert second['supervisor']['requests'] == 0
                assert second['supervisor']['status'] == 'not_configured'
                assert 'AI belum terhubung' in page.inner_text('#aiNote')
                for width in (1440, 768, 390, 360):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.wait_for_timeout(180)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
                    screenshot = OUTPUT / f'hybrid-{width}.png'
                    page.screenshot(path=str(screenshot), full_page=True)
                    evidence['screens'].append(str(screenshot))
                page.set_viewport_size({'width': 1440, 'height': 1050})
            evidence['modes'].append({'mode': mode, 'run_id': second['run_id'], 'step': second['step'], 'moving_vehicles': moved})
            page.click('#stop')
            page.wait_for_function('!state.telemetry.running')
            assert not page.is_visible('#comparison')
        page.select_option('#corridor', 'galian_berat')
        page.wait_for_function("state.case.corridor==='galian_berat' && !frames.length")
        page.wait_for_timeout(500)
        assert page.evaluate('state.case.corridor') == 'galian_berat'
        page.select_option('#mode', 'katup')
        page.click('#start')
        page.wait_for_function("state.telemetry.running && state.telemetry.step>=5")
        assert page.evaluate('state.telemetry.case.corridor') == 'galian_berat'
        page.click('#stop')
        page.wait_for_function('!state.telemetry.running')
        page.select_option('#corridor', 'jakarta_pondok_pinang')
        page.wait_for_function("state.case.corridor==='jakarta_pondok_pinang'")
        assert not errors, errors
        browser.close()
    (OUTPUT / 'browser.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


def verify_results():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=os.getenv('KATUP_CHROMIUM'))
        page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
        page.goto(BASE, wait_until='networkidle')
        page.wait_for_selector('#comparison', state='visible')
        payload = page.evaluate("fetch('/api/status').then(r=>r.json())")
        runs = payload['comparison']
        assert payload['telemetry']['finished']
        assert len({run['case']['signature'] for run in runs.values()}) == 1
        assert page.text_content('#comparisonStatus') == '3 mode selesai'
        values = page.locator('#comparisonRows tr').first.locator('td').all_text_contents()
        assert values == [f"{runs[mode]['summary']['completed_trips']:,}".replace(',', '.') for mode in ('baseline', 'katup', 'hybrid')]
        assert page.locator('#comparisonRows tr').count() == 5
        assert 'Mode AI belum memakai saran AI' in page.inner_text('#comparisonMethod')
        assert page.locator('#queueChart,#speedChart,.agent-card,.decision-panel,.events').count() == 0
        baseline, katup = runs['baseline']['summary'], runs['katup']['summary']
        if any(katup.get(key, 0) > baseline.get(key, 0) for key in ('spillback_seconds', 'junction_blocked_seconds', 'avg_duration', 'avg_waitingTime')):
            assert 'tradeoff' in page.get_attribute('#resultVerdict', 'class')
        if katup.get('avg_duration', 0) > baseline.get('avg_duration', 0) + .01:
            assert 'Waktu perjalanan rata-rata trip selesai bertambah' in page.inner_text('#resultVerdict')
        page.screenshot(path=str(OUTPUT / 'finished-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUTPUT / 'finished-mobile.png'), full_page=True)
        page.evaluate("window.savedComparison=structuredClone(state.comparison);state.comparison.katup.seed+=1;renderComparison(state.comparison)")
        assert page.locator('#comparisonRows tr').first.locator('td').nth(1).inner_text() == 'Kondisi berbeda'
        page.evaluate("state.comparison=structuredClone(window.savedComparison);state.comparison.katup.final.run_id='wrong';renderComparison(state.comparison)")
        assert page.locator('#comparisonRows tr').first.locator('td').nth(1).inner_text() == 'Kondisi berbeda'
        page.evaluate("state.comparison=structuredClone(window.savedComparison);state.comparison.hybrid.supervisor.configured=true;state.comparison.hybrid.final.gui_delay_ms=100;renderComparison(state.comparison)")
        assert not page.is_visible('#comparison')
        page.evaluate("state.comparison=structuredClone(window.savedComparison);state.telemetry.run_id='wrong';renderComparison(state.comparison)")
        assert not page.is_visible('#comparison')
        evidence = {'three_finished_modes': True, 'trip_counts': values, 'mismatched_seed_hidden': True, 'mismatched_saved_session_hidden': True, 'mismatched_live_session_hidden': True, 'llm_playback_mismatch_hidden': True}
        (OUTPUT / 'comparison.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps(evidence, indent=2))
        browser.close()


def verify_corridors(corridors=None):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    errors, evidence = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=os.getenv('KATUP_CHROMIUM'))
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE, wait_until='networkidle')
        page.wait_for_function("document.querySelector('#corridor').options.length>=6")
        for corridor in corridors or ('ui_depok', 'akses_ui', 'pasar_rebo', 'tb_simatupang', 'simpang_pasar_rebo', 'kebon_sirih', 'bina_marga'):
            page.select_option('#corridor', corridor)
            page.wait_for_function("(key)=>state.case.corridor===key && state.network.case.corridor===key && document.querySelector('#map').getAttribute('aria-busy')==='false'", arg=corridor)
            case = page.evaluate('state.case')
            assert case['lane_label'] in page.inner_text('#zoneLaneLabel')
            assert 'openstreetmap.org/?mlat=' in page.get_attribute('#mapLocation', 'href')
            if corridor == 'akses_ui':
                assert '1 lajur' in page.inner_text('#zoneLaneLabel')
                assert '→' not in page.inner_text('#zoneLaneLabel')
            if corridor == 'simpang_pasar_rebo':
                assert page.is_visible('#researchNote')
                assert 'belum tersedia' in page.inner_text('#researchNote')
                response = page.request.get(BASE + '/research/simpang_pasar_rebo/datasheet.xlsx')
                assert response.ok and response.body().startswith(b'PK')
                assert '106.865299' in page.get_attribute('#mapLocation', 'href')
            elif corridor == 'kebon_sirih':
                assert page.is_visible('#researchNote')
                assert 'Juli–Agustus 2026' in page.inner_text('#researchNote')
                assert '4 → 2 lajur' in page.inner_text('#zoneLaneLabel')
                assert page.locator('#workzone polyline').count() == 3
                assert 'PEKERJAAN JALAN' in page.text_content('#labels')
                response = page.request.get(BASE + '/research/kebon_sirih/datasheet.xlsx')
                assert response.ok and response.body().startswith(b'PK')
            elif corridor == 'bina_marga':
                assert page.is_visible('#researchNote')
                assert 'masih asumsi' in page.inner_text('#researchNote')
                assert '1 lajur per arah' in page.inner_text('#zoneLaneLabel')
                assert '→' not in page.inner_text('#zoneLaneLabel')
                assert page.locator('#workzone polyline').count() == 5
                response = page.request.get(BASE + '/research/bina_marga/datasheet.xlsx')
                assert response.ok and response.body().startswith(b'PK')
                assert '106.889986' in page.get_attribute('#mapLocation', 'href')
            else:
                assert not page.is_visible('#researchNote')
            page.click('[data-view=all]')
            page.locator('#mapContainer').screenshot(path=str(OUTPUT / f'{corridor}-network.png'))
            page.select_option('#mode', 'hybrid')
            page.select_option('#speed', '100')
            page.click('#start')
            page.wait_for_function('(key)=>state.telemetry.running && state.telemetry.case.corridor===key && state.telemetry.step>=10', arg=corridor)
            previous = page.evaluate('state.telemetry')
            page.wait_for_function('(step)=>state.telemetry.step>step+5', arg=previous['step'])
            current = page.evaluate('state.telemetry')
            positions = {v['id']: (v['x'], v['y']) for v in previous['vehicles_sample']}
            moved = sum(positions[v['id']] != (v['x'], v['y']) for v in current['vehicles_sample'] if v['id'] in positions)
            assert moved > 0
            assert current['supervisor']['requests'] == 0
            assert current['supervisor']['status'] == 'not_configured'
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.click('#stop')
            page.wait_for_function('!state.telemetry.running')
            evidence.append({'corridor': corridor, 'lane_label': case['lane_label'], 'moving_vehicles': moved, 'step': current['step'], 'start_stop': True, 'mobile_no_overflow': True})
        assert not errors, errors
        browser.close()
    report = {'base': BASE, 'corridors': evidence, 'page_errors': errors}
    (OUTPUT / 'regional-browser.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-only', action='store_true')
    parser.add_argument('--all-corridors', action='store_true')
    parser.add_argument('--corridors', nargs='+')
    args = parser.parse_args()
    if args.all_corridors or args.corridors:
        verify_corridors(args.corridors)
    elif args.results_only:
        verify_results()
    else:
        verify()
