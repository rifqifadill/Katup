import html
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import sumolib

from build_corridors import ROOT, context_edges, extend, protected_program
from fetch_corridors import AREAS
from build_workzone import rename_edge


def netconvert_binary():
    local = ROOT / '.runtime-llm/netconvert-1.28/sumo/bin/netconvert'
    binary = os.getenv('KATUP_NETCONVERT') or (str(local) if local.exists() else 'netconvert')
    version = subprocess.check_output([binary, '--version'], text=True)
    match = re.search(r'netconvert (\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (1, 28):
        raise RuntimeError('peta ini perlu netconvert minimal 1.28, jalankan python tools/install_netconvert.py dlu, SUMO runtime tetep bisa versi 1.18')
    return binary


def build_staged():
    corridor = 'bina_marga'
    directory = ROOT / 'scenarios' / corridor
    spec = json.loads((directory / 'spec.json').read_text())
    zone = spec['workzone']
    binary = netconvert_binary()
    common = ['--lefthand', '--no-turnarounds', '--tls.green.time', '40', '--tls.yellow.time', '3', '--tls.allred.time', '2', '--no-warnings']
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        base = temporary / 'base.net.xml'
        subprocess.run([binary, '--osm-files', str(directory / 'source/roads.osm.xml'), '--geometry.remove', '--junctions.join', '--remove-edges.isolated', '--output.street-names', '--keep-edges.in-geo-boundary', ','.join(map(str, AREAS[corridor]['bbox'])), '--output-file', str(base), *common], check=True)
        network = sumolib.net.readNet(str(base))
        paths, rates = [spec['main']], [spec['main_rate']]
        for key in spec['cross']:
            edge = network.getEdge(key)
            before = extend(edge, reverse=True, distance=400, blocked=spec['main'])
            outgoing = [e for e in edge.getAllowedOutgoing('passenger') if e.getID() != spec['entry'] and e.getID() not in before]
            matching = [e for e in outgoing if e.getName() == edge.getName()]
            selected = max(matching or outgoing, key=lambda e: (e.getLaneNumber(), e.getLength(), e.getID()))
            paths.append(before + extend(selected, distance=450, blocked=before))
            rates.append(spec['cross_rate'])
        paths.extend(spec['paths'])
        rates.extend([spec['ambient_rate']] * len(spec['paths']))
        keep = context_edges(network, paths, spec['tls'])
        excluded = set(spec.get('exclude_edges', []))
        if excluded.intersection(key for path in paths for key in path):
            raise ValueError('ruas yg dipakai rute ga boleh dihapus')
        keep -= excluded
        keep_file = temporary / 'keep.txt'
        keep_file.write_text('\n'.join(sorted(keep)))
        first, last = zone['edges'][0], zone['edges'][-1]
        remaining = zone['model_length_m'] - sum(network.getEdge(key).getLength() for key in zone['edges'][:-1]) + zone['start_m']
        if not 10 < remaining < network.getEdge(last).getLength() - 10:
            raise ValueError('ujung zona pekerjaan ga muat pada ruas sumber')
        patch = ET.Element('edges')
        edge = ET.SubElement(patch, 'edge', id=first)
        ET.SubElement(edge, 'split', pos=str(zone['start_m']), idBefore='katup_buffer', idAfter='katup_work', lanes='0')
        edge = ET.SubElement(patch, 'edge', id=last)
        ET.SubElement(edge, 'split', pos=str(round(remaining, 2)), idBefore='katup_work_end', idAfter='katup_exit', lanes='0')
        patch_file = temporary / 'workzone.edg.xml'
        ET.ElementTree(patch).write(patch_file, encoding='utf-8', xml_declaration=True)
        target = directory / 'network.net.xml'
        subprocess.run([binary, '--sumo-net-file', str(base), '--edge-files', str(patch_file), '--keep-edges.input-file', str(keep_file), '--tls.set', spec['tls'], '--output-file', str(target), *common], check=True)
    def replace(path):
        return [part for key in path for part in (['katup_buffer', 'katup_work'] if key == first else ['katup_work_end', 'katup_exit'] if key == last else ['katup_pre'] if key == spec['entry'] else [key])]
    work_edges = ['katup_work', *zone['edges'][1:-1], 'katup_work_end']
    tree = ET.parse(target)
    root = tree.getroot()
    rename_edge(root, spec['entry'], 'katup_pre')
    for edge in root.findall('edge'):
        if edge.get('name'):
            edge.set('name', html.unescape(edge.get('name')))
        for lane in edge.findall('lane'):
            lane.set('speed', str(zone['speed_kmh'] / 3.6 if edge.get('id') in work_edges else min(13.89, float(lane.get('speed')))))
            if edge.get('id') in work_edges:
                lane.set('width', str(zone['lane_width_m']))
    tls, phases = protected_program(root, spec['tls'], spec['west'])
    ET.indent(root, space='    ')
    tree.write(target, encoding='utf-8', xml_declaration=True)
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', id='car', vClass='passenger', length='4.6', width='1.8', minGap='2.5', accel='2.6', decel='4.5', sigma='0.5')
    for index, (path, rate) in enumerate(zip(paths, rates)):
        ET.SubElement(routes, 'route', id=f'route_{index}', edges=' '.join(replace(path)))
        ET.SubElement(routes, 'flow', id=f'flow_{index}', route=f'route_{index}', type='car', begin='0', end='1800', vehsPerHour=str(rate), departLane='best', departSpeed='max')
    ET.indent(routes, space='    ')
    ET.ElementTree(routes).write(directory / 'demand.rou.xml', encoding='utf-8', xml_declaration=True)
    pre_edges = replace(spec['main'][spec['main'].index(spec['entry']):spec['main'].index(first)]) + ['katup_buffer']
    detectors = {'farwest': spec['decision']}
    groups = {'pre': [], 'farwest': ['farwest']}
    for number, edge in enumerate(pre_edges):
        sensor = 'pre' if number == 0 else f'pre_{number}'
        detectors[sensor] = edge
        groups['pre'].append(sensor)
    approaches = {}
    for index, key in enumerate([spec['west'], *spec['cross']]):
        prefix = 'west' if index == 0 else f'cross_{index}'
        edges = extend(network.getEdge(key), reverse=True, distance=300)
        approaches[key] = edges
        groups[prefix] = []
        for number, edge in enumerate(edges):
            sensor = prefix if number == 0 else f'{prefix}_{number}'
            detectors[sensor] = edge
            groups[prefix].append(sensor)
    profile = {'id': corridor, 'name': AREAS[corridor]['name'], 'geographic': True, 'duration': 1800, 'tls': tls, 'junction': spec['tls'], 'pre': 'katup_pre', 'pre_edges': pre_edges, 'west': spec['west'], 'decision': spec['decision'], 'bottleneck': 'katup_work', 'bottleneck_edges': work_edges, 'north': spec['cross'][:1], 'south': spec['cross'][1:], 'detectors': detectors, 'detector_groups': groups, 'approach_edges': approaches, 'cross_detectors': [f'cross_{i}' for i in range(1, len(spec['cross']) + 1)], 'main': replace(spec['main'])[1:], 'paths': spec['paths'], 'route_names': spec['route_names'], 'phases': phases, 'context': spec['context'], 'map_attribution': '© OpenStreetMap contributors · ODbL', 'center': spec['center'], 'requested_point': spec['requested_point'], 'bbox': AREAS[corridor]['bbox'], 'source_edge': first, 'source_road': spec['road'], 'workzone_type': 'staged_speed_restriction', 'workzone_label': 'GALIAN UJI', 'lane_label': '1 lajur per arah · hambatan uji', 'signal_note': 'Lampu eksperimen di simpang Gempol–Ceger–Bina Marga, bukan APILL terverifikasi atau petugas buka-tutup proyek', 'context_edge_limit': 400, 'workzone': zone, 'research': spec['research'], 'default_view': 'bottleneck', 'model_note': 'Model hambatan pada arus ke Cipayung, bukan replika satu lajur bersama dan buka-tutup aktual', 'build': {'netconvert': subprocess.check_output([binary, '--version'], text=True).splitlines()[0], 'runtime_tested': 'SUMO 1.18.0'}}
    (directory / 'profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
    print(corridor, 'ready', len(work_edges), 'potongan galian uji, arah balik tetap ada', flush=True)
