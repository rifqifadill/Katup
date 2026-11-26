import argparse
from collections import deque
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.append(str(Path(os.environ.get('SUMO_HOME', '/usr/share/sumo')) / 'tools'))
import sumolib

from fetch_corridors import AREAS

ROOT = Path(__file__).resolve().parents[1]


def extend(edge, reverse=False, distance=450, blocked=()):
    path = [edge]
    length = edge.getLength()
    used = {edge.getID(), *blocked}
    while length < distance and len(path) < 18:
        current = path[0] if reverse else path[-1]
        candidates = current.getIncoming() if reverse else current.getAllowedOutgoing('passenger')
        candidates = [e for e in candidates if e.allows('passenger') and e.getID() not in used and (not reverse or current in e.getAllowedOutgoing('passenger'))]
        if not candidates:
            break
        matching = [e for e in candidates if e.getName() == edge.getName() and e.getName()]
        selected = max(matching or candidates, key=lambda e: (e.getLaneNumber(), e.getLength(), e.getID()))
        if reverse:
            path.insert(0, selected)
        else:
            path.append(selected)
        used.add(selected.getID())
        length += selected.getLength()
    return [e.getID() for e in path]


def context_edges(network, routes, junction, limit=400):
    keep = {edge for route in routes for edge in route}
    node = network.getNode(junction)
    keep.update(e.getID() for e in node.getIncoming() + node.getOutgoing() if e.allows('passenger'))
    pending = deque(sorted(keep))
    while pending and len(keep) < limit:
        current = network.getEdge(pending.popleft())
        neighbors = set(current.getFromNode().getIncoming() + current.getFromNode().getOutgoing() + current.getToNode().getIncoming() + current.getToNode().getOutgoing())
        for edge in sorted(neighbors, key=lambda e: e.getID()):
            if edge.allows('passenger') and edge.getID() not in keep:
                keep.add(edge.getID())
                pending.append(edge.getID())
                if len(keep) >= limit:
                    break
    return keep


def protected_program(root, junction, west):
    connections = [c for c in root.findall('connection') if c.get('from') == west and c.get('to') == 'katup_pre' and c.get('tl')]
    if not connections:
        raise ValueError('Gerakan utama belum terhubung ke sinyal')
    tls = connections[0].get('tl')
    logic = root.find(f"tlLogic[@id='{tls}']")
    old_states = [p.get('state') for p in logic.findall('phase')]
    size = len(old_states[0])
    controlled = [c for c in root.findall('connection') if c.get('tl') == tls]
    groups = [west] + sorted({c.get('from') for c in controlled} - {west})
    if len(groups) < 2:
        raise ValueError('Simpang membutuhkan lebih dari satu pendekat')
    for phase in logic.findall('phase'):
        logic.remove(phase)
    logic.set('type', 'static')
    logic.set('programID', 'katup_lab')
    logic.set('offset', '0')
    served, movement = {}, []
    main_links = {int(c.get('linkIndex')) for c in connections}
    for index, edge in enumerate(groups):
        green = ['r'] * size
        yellow = ['r'] * size
        for connection in controlled:
            if connection.get('from') == edge:
                link = int(connection.get('linkIndex'))
                green[link] = 'G' if any(state[link] == 'G' for state in old_states) else 'g'
                yellow[link] = 'y'
        served[str(index * 3)] = [edge]
        for duration, state in ((40, ''.join(green)), (3, ''.join(yellow)), (2, 'r' * size)):
            ET.SubElement(logic, 'phase', duration=str(duration), state=state)
            movement.append('green' if any(state[i] in 'gG' for i in main_links) else 'yellow' if any(state[i] == 'y' for i in main_links) else 'red')
    for other in list(root.findall('tlLogic')):
        if other is not logic and other.get('id') == tls:
            root.remove(other)
    return tls, {'main': [0], 'cross': [i * 3 for i in range(1, len(groups))], 'served': served, 'movement_states': movement}


def build(corridor):
    area = AREAS[corridor]
    directory = ROOT / 'scenarios' / corridor
    spec = json.loads((directory / 'spec.json').read_text())
    common = ['--lefthand', '--no-turnarounds', '--tls.green.time', '40', '--tls.yellow.time', '3', '--tls.allred.time', '2', '--no-warnings']
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary) / 'base.net.xml'
        subprocess.run(['netconvert', '--osm-files', str(directory / 'source/roads.osm.xml'), '--geometry.remove', '--junctions.join', '--remove-edges.isolated', '--output.street-names', '--keep-edges.in-geo-boundary', ','.join(map(str, area['bbox'])), '--output-file', str(base), *common], check=True)
        network = sumolib.net.readNet(str(base))
        original = network.getEdge(spec['edge'])
        paths = [spec['main']]
        rates = [1200 if original.getLaneNumber() == 1 else 1500]
        for edge_id in spec['cross']:
            edge = network.getEdge(edge_id)
            before = extend(edge, reverse=True, blocked=spec['main'], distance=400)
            outgoing = [e for e in edge.getAllowedOutgoing('passenger') if e.getID() != spec['edge'] and e.getID() not in before]
            if not outgoing:
                outgoing = [e for e in edge.getAllowedOutgoing('passenger') if e.getID() not in before]
            if not outgoing:
                raise ValueError(f'Tidak ada keluaran untuk arus silang {edge_id}')
            matching = [e for e in outgoing if e.getName() == edge.getName() and e.getName()]
            selected = max(matching or outgoing, key=lambda e: (e.getLaneNumber(), e.getLength(), e.getID()))
            route = before + extend(selected, blocked=before, distance=450)
            paths.append(route)
            rates.append(350)
        paths.extend(spec['paths'])
        rates.extend([120] * len(spec['paths']))
        keep = context_edges(network, paths, spec['tls'])
        edge_file = Path(temporary) / 'keep-edges.txt'
        edge_file.write_text('\n'.join(sorted(keep)))
        length = original.getLength()
        pre_length = min(180, length * .5)
        work_length = min(180, length - pre_length)
        exit_exists = length - pre_length - work_length >= 60
        passenger_lane = next(lane.getIndex() for lane in original.getLanes() if lane.allows('passenger'))
        patch = ET.Element('edges')
        edge = ET.SubElement(patch, 'edge', id=spec['edge'])
        ET.SubElement(edge, 'split', pos=str(round(pre_length, 2)), idBefore='katup_pre', idAfter='katup_work', lanes=str(passenger_lane))
        replacements = ['katup_pre', 'katup_work']
        if exit_exists:
            ET.SubElement(edge, 'split', pos=str(round(pre_length + work_length, 2)), idBefore='katup_work', idAfter='katup_exit', lanes=' '.join(str(i) for i in range(original.getLaneNumber())))
            replacements.append('katup_exit')
        patch_file = Path(temporary) / 'workzone.edg.xml'
        ET.ElementTree(patch).write(patch_file, encoding='utf-8', xml_declaration=True)
        target = directory / 'network.net.xml'
        subprocess.run(['netconvert', '--sumo-net-file', str(base), '--edge-files', str(patch_file), '--keep-edges.input-file', str(edge_file), '--tls.set', spec['tls'], '--output-file', str(target), *common], check=True)
    tree = ET.parse(target)
    root = tree.getroot()
    for edge in root.findall('edge'):
        if edge.get('name'):
            edge.set('name', html.unescape(edge.get('name')))
        for lane in edge.findall('lane'):
            lane.set('speed', str(min(13.89, float(lane.get('speed')))))
            if edge.get('id') == 'katup_work':
                lane.set('speed', '1.39')
                if original.getLaneNumber() == 1:
                    lane.set('width', '2.4')
    tls, phases = protected_program(root, spec['tls'], spec['west'])
    ET.indent(root, space='    ')
    tree.write(target, encoding='utf-8', xml_declaration=True)
    def replace(route):
        return [part for edge in route for part in (replacements if edge == spec['edge'] else [edge])]
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', id='car', vClass='passenger', length='4.6', minGap='2.5', accel='2.6', decel='4.5', sigma='0.5')
    for index, (path, rate) in enumerate(zip(paths, rates)):
        ET.SubElement(routes, 'route', id=f'route_{index}', edges=' '.join(replace(path)))
        ET.SubElement(routes, 'flow', id=f'flow_{index}', route=f'route_{index}', type='car', begin='0', end='1800', vehsPerHour=str(rate), departLane='best', departSpeed='max')
    ET.indent(routes, space='    ')
    ET.ElementTree(routes).write(directory / 'demand.rou.xml', encoding='utf-8', xml_declaration=True)
    cross = spec['cross']
    detectors = {'pre': 'katup_pre', 'west': spec['west'], 'farwest': spec['decision'], 'north': cross[0], 'south': cross[1] if len(cross) > 1 else cross[0]}
    cross_detectors = ['north'] + (['south'] if len(cross) > 1 else [])
    for index, edge in enumerate(cross[2:], 2):
        detectors[f'cross_{index}'] = edge
        cross_detectors.append(f'cross_{index}')
    context = 'Geometri OpenStreetMap, volume kendaraan, zona galian, dan sinyal merupakan skenario eksperimen'
    profile = {'id': corridor, 'name': area['name'], 'geographic': True, 'duration': 1800, 'tls': tls, 'junction': spec['tls'], 'pre': 'katup_pre', 'west': spec['west'], 'decision': spec['decision'], 'bottleneck': 'katup_work', 'north': cross[:1], 'south': cross[1:], 'detectors': detectors, 'cross_detectors': cross_detectors, 'main': replace(spec['main'])[1:], 'paths': spec['paths'], 'route_names': spec['route_names'], 'phases': phases, 'context': context, 'map_attribution': '© OpenStreetMap contributors · ODbL', 'center': spec['center'], 'bbox': area['bbox'], 'source_edge': spec['edge'], 'source_road': spec['road'], 'workzone_type': 'lane_drop' if original.getLaneNumber() > 1 else 'speed_restriction', 'signal_note': 'Sinyal eksperimen melayani satu pendekat bergantian, hijau 40 s, kuning 3 s, semua-merah 2 s, bukan rekaman APILL lapangan', 'context_edge_limit': 400}
    (directory / 'profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding='utf-8')
    print(corridor, 'ready', 'lanes', original.getLaneNumber(), '→ 1', 'phases', len(phases['movement_states']), 'detours', len(spec['paths']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('corridors', nargs='+', choices=list(AREAS))
    args = parser.parse_args()
    for corridor in args.corridors:
        build(corridor)
