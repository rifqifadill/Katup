"""Run paired scenarios with identical inputs and verify the baseline signal."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('SUMO_HOME', '/usr/share/sumo')
import katup_controller as controller
from katup_scenario import build_scenario, case_metadata

parser = argparse.ArgumentParser()
parser.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 42])
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
build_scenario()
case = case_metadata()
network = ET.parse(ROOT / 'scenarios/galian_berat/network.net.xml').getroot()
phases = network.find("tlLogic[@id='titik_urai']").findall('phase')
for link in range(15):
    for states, expected in [('Gg', 40), ('yY', 3), ('rR', 47)]:
        assert sum(float(phase.get('duration')) for phase in phases if phase.get('state')[link] in states) == expected
original_start = controller.traci.start
report = {'case': case, 'runs': []}
for seed in args.seeds:
    for mode in ('baseline', 'katup'):
        tripfile = args.output / f'{mode}-{seed}.tripinfo.xml'
        def start(command, *a, **kw):
            return original_start(command + ['--seed', str(seed), '--tripinfo-output', str(tripfile), '--no-step-log', 'true'], *a, **kw)
        controller.traci.start = start
        phase_log = []
        def inspect(step, metrics, valve, route, recorder):
            phase = controller.traci.trafficlight.getPhase(controller.TLS_ID)
            phase_log.append(phase)
            if mode == 'baseline':
                expected_phase = next(i for i, boundary in enumerate((40, 43, 45, 85, 88, 90)) if (step - 1) % 90 < boundary)
                assert phase == expected_phase, (step, phase, expected_phase)
        system = controller.run_simulation(mode == 'katup', False, on_step=inspect)
        trips = ET.parse(tripfile).getroot().findall('tripinfo')
        summary = {'completed_trips': len(trips), **system}
        for metric in ('duration', 'waitingTime', 'timeLoss', 'departDelay'):
            summary[f'avg_{metric}'] = statistics.mean(float(t.get(metric)) for t in trips)
        assert summary['arrived'] + summary['running'] + summary['pending'] == case['planned_vehicles'], summary
        assert summary['collisions'] == 0 and summary['teleports'] == 0, summary
        run = {'mode': mode, 'seed': seed, 'summary': summary}
        report['runs'].append(run)
        (args.output / 'report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(run), flush=True)
