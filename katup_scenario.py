"""Reproducible heavy-roadworks case shared by baseline and KATUP."""
from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / 'progress_tahapan/05_visual_urban_enhancements'
CASE_DIR = ROOT / 'scenarios/galian_berat'
CASE_NAME = 'Galian berat · arus utama 1.500 kendaraan/jam'
DURATION = 1800
DETECTOR_EDGES = {
    'pre': 'edge_pre_bottle',
    'west': 'edge_W2J',
    'north': 'edge_N2J',
    'south': 'edge_S2J',
    'farwest': 'edge_W_far2W',
}


def write_xml(path, root):
    ET.indent(root, space='    ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def build_scenario():
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    network = ET.parse(SOURCE_DIR / 'katup.net.xml').getroot()
    for lane in network.findall("edge[@id='edge_bottleneck']/lane"):
        lane.set('speed', '1.39')
    phases = network.find("tlLogic[@id='titik_urai']").findall('phase')
    phases[3].set('state', 'rrrrrrrrrrGGgGG')
    phases[4].set('state', 'rrrrrrrrrryyyyy')
    # Stress-case assumption: drivers may enter the box despite a blocked exit.
    # This applies to both modes. KATUP must prevent the blockage through control.
    for connection in network.findall('connection'):
        if connection.get('to') == 'edge_pre_bottle' and connection.get('tl') == 'titik_urai':
            connection.set('keepClear', '0')
    write_xml(CASE_DIR / 'network.net.xml', network)

    routes = ET.parse(SOURCE_DIR / 'katup.rou.xml').getroot()
    routes.find("route[@id='route_main']").set('edges',
        'edge_W_far2W edge_W2J edge_pre_bottle edge_bottleneck '
        'edge_bottle_exit edge_post_merge edge_E2CBD')
    for flow in routes.findall('flow'):
        flow.set('end', str(DURATION))
        flow.set('departLane', 'random')
    write_xml(CASE_DIR / 'demand.rou.xml', routes)

    detectors = ET.Element('additional')
    for prefix, edge in DETECTOR_EDGES.items():
        for lane in network.findall(f"edge[@id='{edge}']/lane"):
            ET.SubElement(detectors, 'laneAreaDetector', {
                'id': f"{prefix}_{lane.get('index')}", 'lane': lane.get('id'),
                'pos': '0', 'length': str(float(lane.get('length')) - 0.1),
                'timeThreshold': '1', 'speedThreshold': '1.39', 'jamThreshold': '10',
                'freq': '60', 'file': '/dev/null',
            })
    write_xml(CASE_DIR / 'detectors.add.xml', detectors)
    config = ET.Element('configuration')
    inputs = ET.SubElement(config, 'input')
    ET.SubElement(inputs, 'net-file', value='network.net.xml')
    ET.SubElement(inputs, 'route-files', value='demand.rou.xml')
    ET.SubElement(inputs, 'additional-files', value='detectors.add.xml')
    timing = ET.SubElement(config, 'time')
    ET.SubElement(timing, 'begin', value='0')
    ET.SubElement(timing, 'end', value=str(DURATION))
    ET.SubElement(timing, 'step-length', value='1')
    processing = ET.SubElement(config, 'processing')
    ET.SubElement(processing, 'time-to-teleport', value='-1')
    write_xml(CASE_DIR / 'simulation.sumocfg', config)
    return CASE_DIR / 'simulation.sumocfg'


def case_metadata():
    digest = sha256()
    for name in ('network.net.xml', 'demand.rou.xml', 'detectors.add.xml', 'simulation.sumocfg'):
        digest.update((CASE_DIR / name).read_bytes())
    digest.update((ROOT / 'katup_controller.py').read_bytes())
    return {
        'name': CASE_NAME, 'signature': digest.hexdigest()[:16],
        'duration': DURATION, 'planned_vehicles': 1590,
        'main_demand_per_hour': 1500, 'total_demand_per_hour': 3180,
        'bottleneck_speed_kmh': 5.004, 'bottleneck_length_m': 142.0,
        'baseline_signal': {'cycle_s': 90, 'green_s': 40, 'yellow_s': 3, 'red_s': 47, 'all_red_s': 2},
        'assumption': 'Pengemudi di arus menuju galian dapat masuk kotak simpang saat hilir padat. Berlaku sama pada kedua mode.',
        'routing': 'Pengalihan 70–90% kandidat yang memenuhi syarat, dengan biaya perjalanan dan kapasitas jalur diperiksa.',
    }


if __name__ == '__main__':
    print(build_scenario())
