import html
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import sumolib

from build_corridors import ROOT, context_edges, extend, protected_program
from fetch_corridors import AREAS


def rename_edge(root, old, new):
    edge = root.find(f"edge[@id='{old}']")
    mapping = {old: new, **{lane.get('id'): f"{new}_{lane.get('index')}" for lane in edge.findall('lane')}}
    for element in root.iter():
        for key in ('id', 'from', 'to', 'lane', 'via', 'incLanes', 'intLanes', 'edges'):
            if key in element.attrib:
                element.set(key, ' '.join(mapping.get(value, value) for value in element.get(key).split()))


def build_historical(corridor):
    directory = ROOT / 'scenarios' / corridor
    spec = json.loads((directory / 'spec.json').read_text())
    zone = spec['workzone']
    common = ['--lefthand', '--no-turnarounds', '--tls.green.time', '40', '--tls.yellow.time', '3', '--tls.allred.time', '2', '--no-warnings']
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        base = temporary / 'base.net.xml'
        subprocess.run(['netconvert', '--osm-files', str(directory / 'source/roads.osm.xml'), '--geometry.remove', '--junctions.join', '--remove-edges.isolated', '--output.street-names', '--keep-edges.in-geo-boundary', ','.join(map(str, AREAS[corridor]['bbox'])), '--output-file', str(base), *common], check=True)
        network = sumolib.net.readNet(str(base))
        main = spec['main']
        paths, rates = [main], [spec['main_rate']]
        for key in spec['cross']:
            edge = network.getEdge(key)
            before = extend(edge, reverse=True, distance=400, blocked=main)
            outgoing = [e for e in edge.getAllowedOutgoing('passenger') if e.getID() != spec['entry'] and e.getID() not in before]
            matching = [e for e in outgoing if e.getName() == edge.getName()]
            selected = max(matching or outgoing, key=lambda e: (e.getLaneNumber(), e.getLength(), e.getID()))
            paths.append(before + extend(selected, distance=450, blocked=before))
            rates.append(spec['cross_rate'])
        paths.extend(spec['paths'])
        rates.extend([spec['ambient_rate']] * len(spec['paths']))
        keep = context_edges(network, paths, spec['tls'])
        keep_file = temporary / 'keep.txt'
        keep_file.write_text('\n'.join(sorted(keep)))
        patch = ET.Element('edges')
        first = ET.SubElement(patch, 'edge', id=zone['edges'][0], numLanes=str(zone['lanes_before']))
        ET.SubElement(first, 'split', pos=str(zone['start_m']), idBefore='katup_buffer', idAfter='katup_work', lanes=' '.join(str(i) for i in range(zone['lanes_during'])))
        for key in zone['edges'][1:]:
            ET.SubElement(patch, 'edge', id=key, numLanes=str(zone['lanes_during']))
        patch_file = temporary / 'historical.edg.xml'
        ET.ElementTree(patch).write(patch_file, encoding='utf-8', xml_declaration=True)
        target = directory / 'network.net.xml'
        subprocess.run(['netconvert', '--sumo-net-file', str(base), '--edge-files', str(patch_file), '--keep-edges.input-file', str(keep_file), '--output-file', str(target), *common], check=True)
    tree = ET.parse(target)
    root = tree.getroot()
    rename_edge(root, spec['entry'], 'katup_pre')
    work_edges = ['katup_work', *zone['edges'][1:]]
    for edge in root.findall('edge'):
        if edge.get('name'):
            edge.set('name', html.unescape(edge.get('name')))
        for lane in edge.findall('lane'):
            lane.set('speed', str(zone['speed_kmh'] / 3.6 if edge.get('id') in work_edges else min(13.89, float(lane.get('speed')))))
    tls, phases = protected_program(root, spec['tls'], spec['west'])
    ET.indent(root, space='    ')
    tree.write(target, encoding='utf-8', xml_declaration=True)
    def replace(path):
        return [part for key in path for part in (['katup_buffer', 'katup_work'] if key == zone['edges'][0] else ['katup_pre'] if key == spec['entry'] else [key])]
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', id='car', vClass='passenger', length='4.6', minGap='2.5', accel='2.6', decel='4.5', sigma='0.5')
    for index, (path, rate) in enumerate(zip(paths, rates)):
        ET.SubElement(routes, 'route', id=f'route_{index}', edges=' '.join(replace(path)))
        ET.SubElement(routes, 'flow', id=f'flow_{index}', route=f'route_{index}', type='car', begin='0', end='1800', vehsPerHour=str(rate), departLane='best', departSpeed='max')
    ET.indent(routes, space='    ')
    ET.ElementTree(routes).write(directory / 'demand.rou.xml', encoding='utf-8', xml_declaration=True)
    pre_edges = replace(main[main.index(spec['entry']):main.index(zone['edges'][0])]) + ['katup_buffer']
    detectors, groups, approaches = {}, {}, {}
    def add_group(prefix, edges):
        groups[prefix] = []
        for index, key in enumerate(edges):
            sensor = prefix if index == 0 else f'{prefix}_{index}'
            detectors[sensor] = key
            groups[prefix].append(sensor)
    add_group('pre', pre_edges)
    add_group('farwest', [spec['decision']])
    for index, key in enumerate([spec['west'], *spec['cross']]):
        prefix = 'west' if index == 0 else f'cross_{index}'
        edges = extend(network.getEdge(key), reverse=True, distance=300)
        approaches[key] = edges
        add_group(prefix, edges)
    profile = {'id': corridor, 'name': AREAS[corridor]['name'], 'geographic': True, 'duration': 1800, 'tls': tls, 'junction': spec['tls'], 'pre': 'katup_pre', 'pre_edges': pre_edges, 'lane_reference_edge': 'katup_buffer', 'west': spec['west'], 'decision': spec['decision'], 'bottleneck': 'katup_work', 'bottleneck_edges': work_edges, 'north': spec['cross'][:1], 'south': spec['cross'][1:], 'detectors': detectors, 'detector_groups': groups, 'approach_edges': approaches, 'cross_detectors': [f'cross_{i}' for i in range(1, len(spec['cross']) + 1)], 'main': replace(main)[1:], 'paths': spec['paths'], 'route_names': spec['route_names'], 'phases': phases, 'context': 'Geometri OpenStreetMap, model historis proyek Juli–Agustus 2026, arus dan sinyal eksperimen', 'map_attribution': '© OpenStreetMap contributors · ODbL', 'center': spec['center'], 'bbox': AREAS[corridor]['bbox'], 'source_edge': zone['edges'][0], 'source_road': spec['road'], 'workzone_type': 'historical_lane_drop', 'workzone_label': 'PEKERJAAN JALAN', 'signal_note': 'Sinyal eksperimen melayani satu pendekat bergantian, hijau 40 s, kuning 3 s, semua-merah 2 s, bukan rekaman APILL lapangan', 'context_edge_limit': 400, 'workzone': zone, 'research': spec['research'], 'default_view': spec['default_view']}
    (directory / 'profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
    print(corridor, 'ready', len(work_edges), 'ruas pekerjaan', zone['lanes_before'], '→', zone['lanes_during'], 'lajur', flush=True)
