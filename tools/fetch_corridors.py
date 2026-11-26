import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AREAS = {
    'ui_depok': {'name': 'Universitas Indonesia–Margonda, Depok', 'bbox': [106.815, -6.383, 106.846, -6.352]},
    'akses_ui': {'name': 'Akses UI–Kelapa Dua, Depok', 'bbox': [106.84, -6.378, 106.869, -6.349]},
    'pasar_rebo': {'name': 'Pasar Rebo–Raya Bogor, Jakarta Timur', 'bbox': [106.852, -6.324, 106.88, -6.296]},
    'simpang_pasar_rebo': {'name': 'Simpang Pasar Rebo–arah Ciliwung', 'bbox': [106.846, -6.32, 106.881, -6.293]},
    'tb_simatupang': {'name': 'TB Simatupang–Tanjung Barat, Jakarta Selatan', 'bbox': [106.817, -6.318, 106.85, -6.292]},
}
ROAD_TYPES = {'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified', 'residential', 'living_street'}


def fetch(corridor):
    area = AREAS[corridor]
    cache = ROOT / '.runtime-llm/map-cache'
    cache.mkdir(parents=True, exist_ok=True)
    nodes, ways, urls = {}, {}, []
    def tile(bbox, depth=0):
        url = 'https://api.openstreetmap.org/api/0.6/map?bbox=' + ','.join(f'{v:.7f}' for v in bbox)
        path = cache / (sha256(url.encode()).hexdigest()[:20] + '.osm.xml')
        if not path.exists():
            try:
                with urlopen(Request(url, headers={'User-Agent': 'KATUP academic SUMO corridor preparation'}), timeout=45) as response:
                    path.write_bytes(response.read())
            except HTTPError as error:
                message = error.read(4000).decode(errors='replace')
                if error.code == 400 and depth < 3 and ('nodes' in message.lower() or 'maximum' in message.lower()):
                    west, south, east, north = bbox
                    midx, midy = (west + east) / 2, (south + north) / 2
                    for smaller in ([west, south, midx, midy], [midx, south, east, midy], [west, midy, midx, north], [midx, midy, east, north]):
                        tile(smaller, depth + 1)
                    return
                raise RuntimeError(f'OSM HTTP {error.code}: {message[:300]}') from None
        source = ET.parse(path).getroot()
        selected = []
        for way in source.findall('way'):
            tags = {t.get('k'): t.get('v') for t in way.findall('tag')}
            if tags.get('highway') in ROAD_TYPES and all(tags.get(k) not in ('no', 'private') for k in ('access', 'motor_vehicle', 'motorcar')):
                selected.append(way)
                key = way.get('id')
                if key not in ways or int(way.get('version', '0')) >= int(ways[key].get('version', '0')):
                    ways[key] = way
        refs = {node.get('ref') for way in selected for node in way.findall('nd')}
        for node in source.findall('node'):
            if node.get('id') in refs:
                nodes[node.get('id')] = node
        urls.append(url)
        print(corridor, len(urls), 'tile', len(ways), 'ruas sumber', flush=True)
    west, south, east, north = area['bbox']
    nx, ny = math.ceil((east - west) / .02), math.ceil((north - south) / .02)
    for x in range(nx):
        for y in range(ny):
            tile([west + (east - west) * x / nx, south + (north - south) * y / ny, west + (east - west) * (x + 1) / nx, south + (north - south) * (y + 1) / ny])
    refs = {node.get('ref') for way in ways.values() for node in way.findall('nd')}
    if refs - nodes.keys():
        raise ValueError('Snapshot belum memiliki seluruh titik geometri jalan')
    directory = ROOT / 'scenarios' / corridor / 'source'
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = ET.Element('osm', version='0.6', generator='KATUP filtered OpenStreetMap snapshot')
    snapshot.extend(nodes[key] for key in sorted(refs, key=int))
    snapshot.extend(ways[key] for key in sorted(ways, key=int))
    ET.ElementTree(snapshot).write(directory / 'roads.osm.xml', encoding='utf-8', xml_declaration=True)
    provenance = {'source': 'OpenStreetMap contributors', 'license': 'ODbL 1.0', 'license_url': 'https://www.openstreetmap.org/copyright', 'urls': urls, 'bbox': area['bbox'], 'fetched_at_utc': datetime.now(timezone.utc).isoformat(), 'filter': sorted(ROAD_TYPES), 'access_filter': 'exclude explicitly private or prohibited motor vehicle roads', 'traffic_source': 'synthetic demand, not measured current traffic', 'osm_ways': len(ways), 'osm_nodes': len(refs), 'snapshot_sha256': sha256((directory / 'roads.osm.xml').read_bytes()).hexdigest()}
    (directory / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('corridors', nargs='+', choices=list(AREAS))
    args = parser.parse_args()
    for corridor in args.corridors:
        fetch(corridor)
