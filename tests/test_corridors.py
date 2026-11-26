import csv
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import sumolib

from katup_core.scenarios import build_case, catalog, get_profile
import katup_controller as controller


ROOT = Path(__file__).resolve().parents[1]
REGIONS = ('ui_depok', 'akses_ui', 'pasar_rebo', 'tb_simatupang', 'simpang_pasar_rebo')


class CorridorTest(unittest.TestCase):
    def test_requested_intersection_faces_west_and_does_not_invent_observations(self):
        config, case = build_case('simpang_pasar_rebo')
        profile = case['profile']
        self.assertEqual(profile['requested_point'], [106.865299, -6.306099])
        lon, lat = profile['center']
        self.assertLess(abs(lon - 106.865299), 0.0005)
        self.assertLess(abs(lat + 6.306099), 0.0005)
        root = ET.parse(config.parent / 'network.net.xml').getroot()
        tls = profile['tls']
        phases = root.find(f"tlLogic[@id='{tls}']").findall('phase')
        links = {int(c.get('linkIndex')) for c in root.findall('connection') if c.get('tl') == tls}
        self.assertEqual(links, set(range(len(phases[0].get('state')))))
        self.assertTrue(all(any(p.get('state')[link] in 'Gg' for p in phases) for link in links))
        shape = root.find("edge[@id='katup_work']/lane").get('shape').split()
        self.assertLess(float(shape[-1].split(',')[0]), float(shape[0].split(',')[0]))
        self.assertEqual(case['pre_lane_count'], 2)
        self.assertEqual(case['bottleneck_lane_count'], 1)
        self.assertEqual(profile['research']['traffic_status'], 'not_available')
        self.assertEqual(profile['research']['excavation_status'], 'unverified')
        source = ET.parse(ROOT / 'scenarios/simpang_pasar_rebo/source/roads.osm.xml').getroot()
        for way in source.findall('way'):
            tags = {t.get('k'): t.get('v') for t in way.findall('tag')}
            self.assertNotIn(tags.get('highway'), ('motorway', 'motorway_link'))
            self.assertNotEqual(tags.get('toll'), 'yes')
        with (ROOT / 'data/simpang_pasar_rebo/weekly_observations.csv').open(encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len({r['date_wib'] for r in rows}), 7)
        for row in rows:
            self.assertEqual(row['data_status'], 'not_available')
            for field in ('volume_veh_per_hour', 'mean_speed_kmh', 'max_queue_m', 'junction_blocked_seconds', 'excavation_active'):
                self.assertEqual(row[field], 'NA')

    def test_green_main_is_not_cut_for_its_own_queue(self):
        profile = get_profile('akses_ui')
        valve = controller.AgenKatup(profile['tls'])
        valve.last_phase = 0
        with patch.object(controller, 'PROFILE', profile), patch.object(controller.traci.trafficlight, 'getPhase', return_value=0), patch.object(controller.traci.trafficlight, 'setPhase') as change, patch.object(controller.traci.simulation, 'getTime', return_value=31), patch.object(controller.traci.edge, 'getLastStepHaltingNumber', side_effect=lambda edge: 10 if edge == profile['west'] else 0), patch.object(controller.traci.lane, 'getLength', return_value=100), patch.object(controller, 'queue_length', return_value=0):
            valve.apply_control(False, False)
            change.assert_not_called()

    def test_empty_cross_approach_can_end_while_another_approach_waits(self):
        profile = get_profile('akses_ui')
        phase = profile['phases']['cross'][0]
        current = profile['phases']['served'][str(phase)]
        valve = controller.AgenKatup(profile['tls'])
        valve.last_phase = phase
        with patch.object(controller, 'PROFILE', profile), patch.object(controller.traci.trafficlight, 'getPhase', return_value=phase), patch.object(controller.traci.trafficlight, 'setPhase') as change, patch.object(controller.traci.simulation, 'getTime', return_value=13), patch.object(controller.traci.edge, 'getLastStepHaltingNumber', side_effect=lambda edge: 0 if edge in current else 10):
            valve.apply_control(False, False)
            change.assert_called_once_with(profile['tls'], phase + 1)

    def test_all_requested_regions_are_distinct_and_geographic(self):
        ids = {item['id'] for item in catalog()['corridors']}
        self.assertTrue(set(REGIONS) <= ids)
        signatures = set()
        for key in REGIONS:
            with self.subTest(corridor=key):
                _, case = build_case(key)
                profile = case['profile']
                self.assertTrue(case['geographic'])
                west, south, east, north = profile['bbox']
                lon, lat = profile['center']
                self.assertTrue(west <= lon <= east and south <= lat <= north)
                self.assertGreater(case['planned_vehicles'], 0)
                self.assertGreater(case['bottleneck_length_m'], 40)
                self.assertEqual(case['bottleneck_lane_count'], 1)
                signatures.add(case['signature'])
                if key == 'akses_ui':
                    self.assertEqual(case['pre_lane_count'], 1)
                    self.assertNotIn('→', case['lane_label'])
        self.assertEqual(len(signatures), len(REGIONS))

    def test_every_demand_and_detour_is_legal_and_keeps_its_destination(self):
        for key in REGIONS:
            with self.subTest(corridor=key):
                config, case = build_case(key)
                network = sumolib.net.readNet(str(config.parent / 'network.net.xml'))
                profile = case['profile']
                self.assertLessEqual(len(network.getEdges()), 405)
                definitions = ET.parse(config.parent / 'demand.rou.xml').getroot()
                all_routes = [r.get('edges').split() for r in definitions.findall('route')] + profile['paths']
                for route in all_routes:
                    self.assertEqual(len(route), len(set(route)), route)
                    for previous, following in zip(route, route[1:]):
                        outgoing = network.getEdge(previous).getAllowedOutgoing('passenger')
                        self.assertIn(network.getEdge(following), outgoing, (key, previous, following))
                for route in profile['paths']:
                    self.assertEqual(route[0], profile['decision'])
                    self.assertEqual(route[-1], profile['main'][-1])
                    self.assertNotIn(profile['bottleneck'], route)

    def test_protected_signal_groups_preserve_clearance_and_approaches(self):
        for key in REGIONS:
            with self.subTest(corridor=key):
                config, case = build_case(key)
                profile = case['profile']
                root = ET.parse(config.parent / 'network.net.xml').getroot()
                logic = root.find(f"tlLogic[@id='{profile['tls']}']")
                phases = logic.findall('phase')
                connections = [c for c in root.findall('connection') if c.get('tl') == profile['tls']]
                for index in range(0, len(phases), 3):
                    green, yellow, red = phases[index:index + 3]
                    self.assertEqual([float(p.get('duration')) for p in (green, yellow, red)], [40, 3, 2])
                    served = {c.get('from') for c in connections if green.get('state')[int(c.get('linkIndex'))] in 'gG'}
                    self.assertEqual(served, set(profile['phases']['served'][str(index)]))
                    self.assertEqual(set(red.get('state')), {'r'})
                    for link, value in enumerate(green.get('state')):
                        self.assertEqual(yellow.get('state')[link], 'y' if value in 'gG' else 'r')
                self.assertEqual(profile['phases']['served']['0'], [profile['west']])

    def test_source_has_provenance_and_retains_source_road_name(self):
        for key in REGIONS:
            with self.subTest(corridor=key):
                source = ROOT / 'scenarios' / key / 'source'
                provenance = json.loads((source / 'provenance.json').read_text())
                self.assertEqual(provenance['license'], 'ODbL 1.0')
                self.assertTrue(provenance['urls'])
                root = ET.parse(ROOT / 'scenarios' / key / 'network.net.xml').getroot()
                profile = get_profile(key)
                for edge in ('katup_pre', 'katup_work'):
                    self.assertEqual(root.find(f"edge[@id='{edge}']").get('name'), profile['source_road'])


if __name__ == '__main__':
    unittest.main()
