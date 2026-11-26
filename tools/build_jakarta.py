import heapq
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.append('/usr/share/sumo/tools')
import sumolib

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'scenarios/jakarta_pondok_pinang'
TLS = 'cluster_305182956_5647027166'


def alternative_paths(network, start, destination):
    pending = [(0, [start])]
    found = []
    while pending and len(found) < 6:
        cost, path = heapq.heappop(pending)
        edge = network.getEdge(path[-1])
        if edge.getID() == destination:
            if not found or len(set(path) - set(found[0])) >= 5:
                found.append(path)
            continue
        if len(path) >= 24:
            continue
        for following in edge.getOutgoing():
            if following.getID() not in path and following.getID() not in ('katup_pre', 'katup_work') and following.allows('passenger'):
                heapq.heappush(pending, (cost + following.getLength() / max(1, following.getSpeed()), path + [following.getID()]))
    return found[:2]


def build():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory) / 'base.net.xml'
        common = ['--lefthand', '--no-turnarounds', '--tls.green.time', '40', '--tls.yellow.time', '3', '--tls.allred.time', '2', '--no-warnings']
        subprocess.run(['netconvert', '--osm-files', str(DIRECTORY / 'source/roads.osm.xml'), '--geometry.remove', '--junctions.join', '--remove-edges.isolated', '--output.street-names', '--output-file', str(base), *common], check=True)
        patch = Path(directory) / 'workzone.edg.xml'
        patch.write_text('<edges><edge id="521441426"><split pos="220" idBefore="katup_pre" idAfter="katup_work" lanes="0"/></edge></edges>')
        subprocess.run(['netconvert', '--sumo-net-file', str(base), '--edge-files', str(patch), '--tls.set', TLS, '--output-file', str(DIRECTORY / 'network.net.xml'), *common], check=True)
    tree = ET.parse(DIRECTORY / 'network.net.xml')
    root = tree.getroot()
    for lane in root.findall('edge/lane'):
        lane.set('speed', str(min(13.89, float(lane.get('speed')))))
    for lane in root.findall("edge[@id='katup_work']/lane"):
        lane.set('speed', '1.39')
    ET.indent(root, space='    ')
    tree.write(DIRECTORY / 'network.net.xml', encoding='utf-8', xml_declaration=True)
    network = sumolib.net.readNet(str(DIRECTORY / 'network.net.xml'))
    decision, destination = '358846360#1', '358846361#2'
    def route(start, end):
        edges, _ = network.getShortestPath(network.getEdge(start), network.getEdge(end), vClass='passenger')
        if not edges:
            raise ValueError(f'Rute {start} ke {end} terputus')
        return [e.getID() for e in edges]
    main = route(decision, 'katup_pre')[:-1] + route('katup_pre', destination)
    paths = alternative_paths(network, decision, destination)
    if len(paths) < 2:
        raise ValueError('Dua jalur alternatif harus tersedia')
    profile = {'id': 'jakarta_pondok_pinang', 'name': 'Pondok Pinang–Pondok Indah, Jakarta', 'geographic': True, 'duration': 1800, 'tls': TLS, 'pre': 'katup_pre', 'west': '-311490299#2', 'decision': decision, 'bottleneck': 'katup_work', 'north': ['27795091'], 'south': ['311490299#0'], 'detectors': {'pre': 'katup_pre', 'west': '-311490299#2', 'farwest': decision, 'north': '27795091', 'south': '311490299#0'}, 'main': main[1:], 'paths': paths, 'route_names': ['Gedung Hijau Raya', 'Niaga Hijau Raya'], 'phases': {'main': [0], 'cross': [3]}, 'context': 'Geometri OpenStreetMap, penutupan 2 menjadi 1 lajur dan arus kendaraan merupakan skenario eksperimen', 'map_attribution': '© OpenStreetMap contributors · ODbL', 'center': [106.781, -6.278], 'signal_note': 'Sinyal simulasi ditambahkan pada simpang Kartika Utama–Metro Alam III, bukan klaim jadwal APILL lapangan'}
    (DIRECTORY / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    flows = [(main, 1500), (route('27795091', '311490299#2'), 350), (route('311490299#0', destination), 350), (route('688707467', '358846361#2'), 200), (route('307011112#0', '32077433#2'), 200), (route('358846354#0', '307011112#2'), 250), (route('1289555828', '358846361#2'), 180), (route('307011112#0', '688688617'), 150)]
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', {'id': 'car', 'vClass': 'passenger', 'length': '4.6', 'minGap': '2.5', 'accel': '2.6', 'decel': '4.5', 'sigma': '0.5'})
    for index, (edges, volume) in enumerate(flows):
        name = f'route_{index}'
        ET.SubElement(routes, 'route', {'id': name, 'edges': ' '.join(edges)})
        ET.SubElement(routes, 'flow', {'id': f'flow_{index}', 'type': 'car', 'route': name, 'begin': '0', 'end': '1800', 'vehsPerHour': str(volume), 'departLane': 'best', 'departSpeed': 'max'})
    ET.indent(routes, space='    ')
    ET.ElementTree(routes).write(DIRECTORY / 'demand.rou.xml', encoding='utf-8', xml_declaration=True)
    print('Main', main)
    print('Alternative routes', paths)


if __name__ == '__main__':
    build()
