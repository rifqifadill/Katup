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
from katup_core.scenarios import build_case, MODES


def evaluate(corridor, demands, seeds, modes, output):
    output.mkdir(parents=True, exist_ok=True)
    original_start = controller.traci.start
    report = {'corridor': corridor, 'llm_provider': os.getenv('KATUP_LLM_PROVIDER', 'disabled'), 'completed': False, 'runs': [], 'method': 'paired inputs, final conservation, yellow/all-red preserved, trips and total vehicle-hours measured'}
    for demand in demands:
        config, case = build_case(corridor, demand)
        network = ET.parse(config.parent / 'network.net.xml').getroot()
        logic = network.find(f"tlLogic[@id='{case['profile']['tls']}']")
        phase_states = [p.get('state') for p in logic.findall('phase')]
        phase_lengths = [float(p.get('duration')) for p in logic.findall('phase')]
        for seed in seeds:
            for mode in modes:
                tripfile = output / f'{corridor}-{demand}-{seed}-{mode}.tripinfo.xml'
                def start(command, *args, **kwargs):
                    return original_start(command + ['--seed', str(seed), '--tripinfo-output', str(tripfile), '--no-step-log', 'true'], *args, **kwargs)
                controller.traci.start = start
                previous = {'phase': None, 'time': 0}
                evidence = {'phase_checks': 0, 'rerouted': 0, 'supervisor': {}}
                def inspect(step, metrics, valve, route, recorder):
                    phase = controller.traci.trafficlight.getPhase(case['profile']['tls'])
                    if step == 1:
                        evidence['sumo_version'] = controller.traci.getVersion()[1]
                    if previous['phase'] is not None and phase != previous['phase']:
                        old = previous['phase']
                        assert phase == (old + 1) % len(phase_states), (old, phase)
                        if 'y' in phase_states[old].lower() or set(phase_states[old].lower()) == {'r'}:
                            assert step - previous['time'] >= phase_lengths[old], (old, step - previous['time'])
                            evidence['phase_checks'] += 1
                        previous['time'] = step
                    previous['phase'] = phase
                    if mode == 'baseline':
                        boundary, expected = 0, None
                        for index, length in enumerate(phase_lengths):
                            boundary += length
                            if (step - 1) % sum(phase_lengths) < boundary:
                                expected = index
                                break
                        assert phase == expected, (step, phase, expected)
                    evidence['rerouted'] = route.reroute_counter
                    evidence['supervisor'] = route.supervisor.telemetry() if route.supervisor else {'external_decisions': False}
                summary = controller.run_simulation(use_gui=False, corridor=corridor, demand=demand, mode=mode, on_step=inspect, audit_path=output / f'{demand}-{seed}-{mode}.decisions.jsonl')
                trips = ET.parse(tripfile).getroot().findall('tripinfo')
                summary['completed_trips'] = len(trips)
                for key in ('duration', 'waitingTime', 'timeLoss', 'routeLength', 'departDelay'):
                    summary[f'avg_{key}'] = round(statistics.mean(float(t.get(key)) for t in trips), 3) if trips else None
                assert summary['arrived'] + summary['running'] + summary['pending'] == case['planned_vehicles'], summary
                assert summary['collisions'] == 0 and summary['teleports'] == 0, summary
                run = {'scenario': mode, 'seed': seed, 'case': case, 'sumo_version': evidence['sumo_version'], 'summary': summary, 'evidence': evidence}
                report['runs'].append(run)
                (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                print(json.dumps({'demand': demand, 'seed': seed, 'mode': mode, 'summary': summary}), flush=True)
    report['completed'] = True
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corridor', default='jakarta_pondok_pinang')
    parser.add_argument('--demands', nargs='+', default=['peak'])
    parser.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 42])
    parser.add_argument('--modes', nargs='+', choices=list(MODES), default=list(MODES))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--without-api', action='store_true')
    args = parser.parse_args()
    if args.without_api:
        os.environ['KATUP_LLM_PROVIDER'] = 'disabled'
    evaluate(args.corridor, args.demands, args.seeds, args.modes, args.output)
