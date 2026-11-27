import csv
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import sumolib

from katup_core.scenarios import build_case


ROOT = Path(__file__).resolve().parents[1]


class BinaMargaTest(unittest.TestCase):
    def test_workzone_is_near_pin_with_two_way_road_and_explicit_assumptions(self):
        config, case = build_case('bina_marga')
        profile = case['profile']
        self.assertEqual(profile['requested_point'], [106.889986, -6.319669])
        self.assertEqual((case['pre_lane_count'], case['bottleneck_lane_count']), (1, 1))
        self.assertNotIn('→', case['lane_label'])
        self.assertAlmostEqual(case['bottleneck_length_m'], 200, delta=5)
        self.assertGreater(case['pre_length_m'], 400)
        self.assertEqual(len(profile['bottleneck_edges']), 5)
        self.assertEqual(profile['research']['traffic_status'], 'not_available')
        self.assertEqual(profile['research']['excavation_status'], 'project_documented_current_pin_unverified')
        network = sumolib.net.readNet(str(config.parent / 'network.net.xml'))
        first = network.getEdge('katup_work').getShape()[0]
        pin = network.convertLonLat2XY(*profile['requested_point'])
        self.assertLess(sum((a - b) ** 2 for a, b in zip(first, pin)) ** 0.5, 60)
        for edge in ('1303140028#5', '1303140028#4', '1303140028#3'):
            self.assertEqual(network.getEdge(edge).getLaneNumber(), 1)
        self.assertIn('bukan replika', profile['model_note'])
        with (ROOT / 'data/bina_marga/current_conditions.csv').open() as stream:
            row = next(csv.DictReader(stream))
        for field in ('excavation_active', 'open_excavation_length_m', 'volume_veh_per_hour', 'mean_speed_kmh', 'junction_blocked_seconds'):
            self.assertEqual(row[field], 'NA')

    def test_alternative_has_same_destination_and_avoids_narrow_neighborhood_roads(self):
        config, case = build_case('bina_marga')
        profile = case['profile']
        network = sumolib.net.readNet(str(config.parent / 'network.net.xml'))
        self.assertEqual(len(profile['paths']), 1)
        path = profile['paths'][0]
        self.assertEqual(path[0], profile['decision'])
        self.assertEqual(path[-1], profile['main'][-1])
        self.assertFalse(set(path) & set(profile['bottleneck_edges']))
        nodes = [network.getEdge(edge).getFromNode().getID() for edge in path]
        nodes.append(network.getEdge(path[-1]).getToNode().getID())
        self.assertEqual(len(nodes), len(set(nodes)))
        for key in path:
            edge = network.getEdge(key)
            self.assertNotIn(edge.getType(), ('highway.residential', 'highway.living_street', 'highway.motorway', 'highway.motorway_link'))
            self.assertGreaterEqual(min(lane.getWidth() for lane in edge.getLanes()), 1.8)
        names = {network.getEdge(edge).getName() for edge in path}
        self.assertIn('Jalan Mpok Nori', names)
        self.assertIn('Jalan Raya Setu', names)
        self.assertGreater(sum(network.getEdge(edge).getLength() for edge in path), sum(network.getEdge(edge).getLength() for edge in [profile['decision'], *profile['main']]))

    def test_source_checksum_and_signal_are_not_presented_as_field_measurements(self):
        source = ROOT / 'scenarios/bina_marga/source'
        provenance = json.loads((source / 'provenance.json').read_text())
        self.assertEqual(hashlib.sha256((source / 'roads.osm.xml').read_bytes()).hexdigest(), provenance['snapshot_sha256'])
        assumptions = json.loads((ROOT / 'data/bina_marga/simulation_assumptions.json').read_text())
        self.assertFalse(assumptions['lane_drop'])
        self.assertIn('eksperimen', assumptions['control_type'])
        self.assertEqual(assumptions['signal_s']['cycle'], 135)
        config, case = build_case('bina_marga')
        root = ET.parse(config.parent / 'network.net.xml').getroot()
        phases = root.find(f"tlLogic[@id='{case['profile']['tls']}']").findall('phase')
        self.assertEqual(len(phases), 9)
        self.assertEqual(sum(float(phase.get('duration')) for phase in phases), 135)


if __name__ == '__main__':
    unittest.main()
