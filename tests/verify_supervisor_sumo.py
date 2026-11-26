import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('SUMO_HOME', '/usr/share/sumo')

import katup_controller as controller
from katup_core.strategy import PROFILES, Supervisor


class ReplayFixture:
    ready = True

    def __init__(self):
        self.calls = 0

    def public_config(self):
        return {'provider': 'test_fixture', 'model': 'replay', 'configured': True}

    def decide(self, snapshot):
        self.calls += 1
        if self.calls == 2:
            raise ValueError('api_unreachable_or_timeout')
        data = {key: snapshot[key] for key in ('run_id', 'simulation_time')}
        data.update(profile=list(PROFILES)[self.calls % len(PROFILES)], route_bias='auto', reason='Respons tiruan untuk uji integrasi, bukan keputusan API nyata')
        if self.calls == 1:
            data['phase'] = 99
        return data, {'input': 20, 'output': 15}


def verify():
    output = ROOT / 'output/supervisor-fixture'
    output.mkdir(parents=True, exist_ok=True)
    original = controller.traci.start
    def start(command, *args, **kwargs):
        return original(command + ['--seed', '42', '--no-step-log', 'true'], *args, **kwargs)
    supervisor = Supervisor('fixture-integration', ReplayFixture(), audit_path=output / 'decisions.jsonl')
    profiles = set()
    def inspect(step, metrics, valve, route, recorder):
        assert valve.strategy == route.strategy
        assert valve.strategy.profile in PROFILES
        profiles.add(valve.strategy.profile)
    with patch.object(controller, 'Supervisor', return_value=supervisor), patch.object(controller.traci, 'start', start):
        summary = controller.run_simulation(use_gui=False, corridor='jakarta_pondok_pinang', mode='hybrid', run_id='fixture-integration', on_step=inspect)
    assert supervisor.stats['accepted'] > 0, supervisor.stats
    assert supervisor.stats['rejected'] >= 1 and supervisor.stats['errors'] >= 1, supervisor.stats
    assert len(profiles) == 4, profiles
    assert summary['collisions'] == summary['teleports'] == 0, summary
    evidence = {'source': 'replay fixture, no external API requests', 'profiles_applied': sorted(profiles), 'supervisor': supervisor.telemetry(), 'summary': summary}
    (output / 'report.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in evidence.items() if key != 'supervisor'}))


if __name__ == '__main__':
    verify()
