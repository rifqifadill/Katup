from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from katup_scenario import build_scenario as build_legacy

ROOT = Path(__file__).resolve().parents[1]
DEMANDS = {'light': ('Lengang', 0.45), 'peak': ('Jam sibuk', 1.0), 'surge': ('Lonjakan arus', 1.3), 'bypass_busy': ('Jalur alternatif padat', 1.0)}
MODES = {'baseline': 'Tanpa KATUP', 'katup': 'KATUP Heuristik', 'hybrid': 'KATUP Hybrid'}
GEOGRAPHIC_CORRIDORS = ('kebon_sirih', 'ui_depok', 'akses_ui', 'simpang_pasar_rebo', 'pasar_rebo', 'tb_simatupang', 'jakarta_pondok_pinang')


def get_profile(corridor='galian_berat'):
    if corridor in GEOGRAPHIC_CORRIDORS:
        return json.loads((ROOT / 'scenarios' / corridor / 'profile.json').read_text())
    if corridor != 'galian_berat':
        raise ValueError('Koridor tidak dikenal')
    return {
        'id': corridor, 'name': 'Koridor uji galian berat', 'geographic': False, 'duration': 1800,
        'tls': 'titik_urai', 'pre': 'edge_pre_bottle', 'west': 'edge_W2J', 'decision': 'edge_W_far2W', 'bottleneck': 'edge_bottleneck',
        'north': ['edge_N2J'], 'south': ['edge_S2J'],
        'detectors': {'pre': 'edge_pre_bottle', 'west': 'edge_W2J', 'farwest': 'edge_W_far2W', 'north': 'edge_N2J', 'south': 'edge_S2J'},
        'route_names': ['Utara', 'Boulevard timur', 'Selatan'],
        'paths': [
            ['edge_W_far2W', 'edge_W2NW', 'edge_NW2N', 'edge_alt_1', 'edge_alt_2', 'edge_post_merge', 'edge_E2CBD'],
            ['edge_W_far2W', 'edge_W2NW', 'edge_NW2N', 'edge_alt_1', 'edge_alt2NE_east', 'edge_NE_east2E', 'edge_E2CBD'],
            ['edge_W_far2W', 'edge_W2SW', 'edge_SW2S', 'edge_S2SE', 'edge_SE2E', 'edge_E2CBD']],
        'main': ['edge_W2J', 'edge_pre_bottle', 'edge_bottleneck', 'edge_bottle_exit', 'edge_post_merge', 'edge_E2CBD'],
        'phases': {'main': [3], 'cross': [0]}, 'context': 'Jaringan sintetik untuk pengujian terkontrol',
    }


def catalog():
    corridors = [get_profile(key) for key in GEOGRAPHIC_CORRIDORS if (ROOT / 'scenarios' / key / 'profile.json').exists()]
    corridors.append(get_profile('galian_berat'))
    return {'corridors': [{key: p[key] for key in ('id', 'name', 'geographic', 'context')} for p in corridors], 'demands': [{'id': key, 'name': value[0]} for key, value in DEMANDS.items()], 'modes': MODES}


def write_xml(path, element):
    ET.indent(element, space='    ')
    content = ET.tostring(element, encoding='utf-8', xml_declaration=True)
    if not path.exists() or path.read_bytes() != content:
        temporary = path.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_bytes(content)
        temporary.replace(path)


@lru_cache(maxsize=16)
def build_case(corridor='galian_berat', demand='peak'):
    if demand not in DEMANDS:
        raise ValueError('Pola arus tidak dikenal')
    profile = get_profile(corridor)
    if corridor == 'galian_berat':
        build_legacy()
    source = ROOT / 'scenarios' / corridor
    directory = ROOT / 'scenarios/generated' / f'{corridor}-{demand}'
    directory.mkdir(parents=True, exist_ok=True)
    network = ET.parse(source / 'network.net.xml').getroot()
    routes = ET.parse(source / 'demand.rou.xml').getroot()
    scale = DEMANDS[demand][1]
    planned = 0
    for flow in routes.findall('flow'):
        number = round(float(flow.get('vehsPerHour')) * scale * profile['duration'] / 3600)
        flow.attrib.pop('vehsPerHour', None)
        flow.set('number', str(number))
        flow.set('end', str(profile['duration']))
        planned += number
    if demand == 'bypass_busy':
        for index, path in enumerate(profile['paths']):
            route_id = f'stress_bypass_{index}'
            ET.SubElement(routes, 'route', {'id': route_id, 'edges': ' '.join(path)})
            ET.SubElement(routes, 'flow', {'id': route_id, 'route': route_id, 'type': 'car', 'begin': '0', 'end': str(profile['duration']), 'number': '80', 'departLane': 'best', 'departSpeed': 'max'})
            planned += 80
    detectors = ET.Element('additional')
    for prefix, edge_id in profile['detectors'].items():
        for lane in network.findall(f"edge[@id='{edge_id}']/lane"):
            ET.SubElement(detectors, 'laneAreaDetector', {'id': f"{prefix}_{lane.get('index')}", 'lane': lane.get('id'), 'pos': '0', 'length': str(max(0.1, float(lane.get('length')) - 0.1)), 'timeThreshold': '1', 'speedThreshold': '1.39', 'jamThreshold': '10', 'freq': '60', 'file': os.devnull})
    write_xml(directory / 'network.net.xml', network)
    write_xml(directory / 'demand.rou.xml', routes)
    write_xml(directory / 'detectors.add.xml', detectors)
    config = ET.Element('configuration')
    inputs = ET.SubElement(config, 'input')
    for tag, value in [('net-file', 'network.net.xml'), ('route-files', 'demand.rou.xml'), ('additional-files', 'detectors.add.xml')]:
        ET.SubElement(inputs, tag, value=value)
    timing = ET.SubElement(config, 'time')
    for tag, value in [('begin', 0), ('end', profile['duration']), ('step-length', 1)]:
        ET.SubElement(timing, tag, value=str(value))
    ET.SubElement(ET.SubElement(config, 'processing'), 'time-to-teleport', value='-1')
    write_xml(directory / 'simulation.sumocfg', config)
    digest = sha256()
    for name in ('network.net.xml', 'demand.rou.xml', 'detectors.add.xml', 'simulation.sumocfg'):
        digest.update((directory / name).read_bytes())
    digest.update(json.dumps(profile, sort_keys=True).encode())
    for name in ('katup_controller.py', 'katup_core/strategy.py', 'katup_core/scenarios.py'):
        digest.update((ROOT / name).read_bytes())
    pre_edge = network.find(f"edge[@id='{profile.get('lane_reference_edge', profile['pre'])}']")
    bottle_edge = network.find(f"edge[@id='{profile['bottleneck']}']")
    pre, bottle = pre_edge.find('lane'), bottle_edge.find('lane')
    pre_lanes, bottle_lanes = len(pre_edge.findall('lane')), len(bottle_edge.findall('lane'))
    lane_label = f'{pre_lanes} → {bottle_lanes} lajur' if pre_lanes != bottle_lanes else f'{bottle_lanes} lajur · hambatan galian'
    pre_length = sum(float(network.find(f"edge[@id='{edge}']/lane").get('length')) for edge in profile.get('pre_edges', [profile['pre']]))
    work_length = sum(float(network.find(f"edge[@id='{edge}']/lane").get('length')) for edge in profile.get('bottleneck_edges', [profile['bottleneck']]))
    info = {'name': profile['name'], 'corridor': corridor, 'demand': demand, 'demand_label': DEMANDS[demand][0], 'duration': profile['duration'], 'planned_vehicles': planned, 'signature': digest.hexdigest()[:16], 'geographic': profile['geographic'], 'data_source': profile['context'], 'traffic_source': 'Arus kendaraan simulasi, belum dikalibrasi dengan data lapangan', 'bottleneck_speed_kmh': round(float(bottle.get('speed')) * 3.6, 1), 'bottleneck_length_m': round(work_length, 2), 'pre_length_m': round(pre_length, 2), 'pre_lane_count': pre_lanes, 'bottleneck_lane_count': bottle_lanes, 'lane_label': lane_label, 'profile': profile}
    return directory / 'simulation.sumocfg', info
