import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import sumolib

import katup_controller as controller
from katup_core.scenarios import build_case


ROOT = Path(__file__).resolve().parents[1]


class KebonSirihTest(unittest.TestCase):
    def test_historical_work_spans_three_edges_and_has_two_legal_detours(self):
        config, case = build_case('kebon_sirih')
        profile = case['profile']
        network = sumolib.net.readNet(str(config.parent / 'network.net.xml'))
        self.assertEqual((case['pre_lane_count'], case['bottleneck_lane_count']), (4, 2))
        self.assertEqual(len(profile['bottleneck_edges']), 3)
        self.assertAlmostEqual(case['bottleneck_length_m'], 345, delta=5)
        self.assertGreater(case['pre_length_m'], 300)
        self.assertLess(network.getEdge(profile['pre']).getLength(), 1)
        for edge in profile['bottleneck_edges']:
            self.assertEqual(network.getEdge(edge).getLaneNumber(), 2)
        self.assertEqual(len(profile['paths']), 2)
        for path in profile['paths']:
            self.assertEqual(path[0], '453439710')
            self.assertEqual(path[-1], '688522170')
            self.assertFalse(set(path) & set(profile['bottleneck_edges']))
            nodes = [network.getEdge(edge).getFromNode().getID() for edge in path]
            nodes.append(network.getEdge(path[-1]).getToNode().getID())
            self.assertEqual(len(nodes), len(set(nodes)))
            for edge in path:
                self.assertNotIn(network.getEdge(edge).getType(), ('highway.motorway', 'highway.motorway_link'))
        root = ET.parse(config.parent / 'detectors.add.xml').getroot()
        self.assertEqual(len(root.findall('laneAreaDetector')), sum(network.getEdge(edge).getLaneNumber() for edge in profile['detectors'].values()))
        assumptions = json.loads((ROOT / 'data/kebon_sirih/simulation_assumptions.json').read_text())
        self.assertEqual(assumptions['project_completed_by'], '2026-08-31')
        self.assertFalse(assumptions['calibrated_to_850m_report'])
        self.assertEqual(profile['research']['traffic_status'], 'qualitative_report_only')

    def test_observer_sums_real_segments_and_weights_occupancy(self):
        profile = {'pre': 'tiny', 'pre_edges': ['tiny', 'road'], 'detectors': {'pre': 'tiny', 'pre_1': 'road'}, 'detector_groups': {'pre': ['pre', 'pre_1']}}
        with patch.object(controller, 'PROFILE', profile), patch.object(controller.traci.edge, 'getLaneNumber', side_effect=lambda edge: 1 if edge == 'tiny' else 2), patch.object(controller.traci.lane, 'getLength', side_effect=lambda lane: 0.2 if lane == 'tiny_0' else 100), patch.object(controller.traci.edge, 'getLastStepVehicleNumber', side_effect=lambda edge: 0 if edge == 'tiny' else 10), patch.object(controller.traci.edge, 'getLastStepHaltingNumber', side_effect=lambda edge: 0 if edge == 'tiny' else 6), patch.object(controller.traci.edge, 'getLastStepMeanSpeed', return_value=5), patch.object(controller.traci.edge, 'getLastStepOccupancy', side_effect=lambda edge: 0 if edge == 'tiny' else 50), patch.object(controller.traci.lanearea, 'getJamLengthMeters', side_effect=lambda sensor: {'pre_0': 0, 'pre_1_0': 30, 'pre_1_1': 50}[sensor]):
            self.assertAlmostEqual(controller.monitored_length(), 100.2)
            self.assertEqual(controller.queue_length('pre'), 50)
            metrics = controller.edge_metrics(controller.pre_edges())
            self.assertEqual(metrics['vehicles'], 10)
            self.assertEqual(metrics['halting'], 6)
            self.assertEqual(metrics['speed_kmh'], 18)
            self.assertAlmostEqual(metrics['occupancy_pct'], 50 * 200 / 200.2)

    def test_signal_reads_upstream_of_tiny_connector_and_keeps_minimum_green(self):
        profile = {'pre': 'tiny', 'pre_edges': ['tiny', 'road'], 'west': 'connector', 'north': ['cross'], 'south': [], 'approach_edges': {'connector': ['approach', 'connector']}, 'phases': {'main': [0], 'cross': [3]}}
        valve = controller.AgenKatup('signal')
        valve.last_phase = 0
        with patch.object(controller, 'PROFILE', profile), patch.object(controller.traci.trafficlight, 'getPhase', return_value=0), patch.object(controller.traci.trafficlight, 'setPhase') as change, patch.object(controller.traci.simulation, 'getTime', return_value=11), patch.object(controller.traci.edge, 'getLastStepHaltingNumber', side_effect=lambda edge: 8 if edge == 'approach' else 0), patch.object(controller.traci.lane, 'getLength', side_effect=lambda lane: 0.2 if lane == 'tiny_0' else 300), patch.object(controller, 'queue_length', return_value=50):
            valve.apply_control(False, False)
            change.assert_not_called()

    def test_shared_corridor_congestion_blocks_both_route_choices(self):
        _, case = build_case('kebon_sirih')
        profile = case['profile']
        common = set(profile['paths'][0][1:-1]) & set(profile['paths'][1][1:-1])
        self.assertIn('1370010732', common)
        with patch.object(controller, 'PROFILE', profile), patch.object(controller.traci.edge, 'getLaneNumber', return_value=2), patch.object(controller.traci.lane, 'getLength', return_value=100), patch.object(controller.traci.edge, 'getTraveltime', return_value=5), patch.object(controller.traci.edge, 'getLastStepVehicleNumber', side_effect=lambda edge: 30 if edge == '1370010732' else 0):
            route = controller.AgenRute()
            route.refresh_routes(0)
            self.assertEqual(route.available, [False, False])


if __name__ == '__main__':
    unittest.main()
