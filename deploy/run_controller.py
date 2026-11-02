"""Linux launcher: preserve the research controller and add runtime telemetry."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('katup_research', ROOT / 'katup_controller.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
os.chdir(ROOT / 'progress_tahapan/05_visual_urban_enhancements')
mode = sys.argv[1] if len(sys.argv) > 1 else 'katup'
if mode not in ('baseline', 'katup'):
    raise SystemExit('Unknown scenario')
state_file = Path(os.environ['KATUP_TELEMETRY'])
start = controller.traci.start

def start_gui(cmd, *args, **kwargs):
    return start(cmd + ['--delay', os.environ.get('KATUP_DELAY', '1000'), '--seed', '42', '--window-size', '1280,800', '--window-pos', '0,0', '--quit-on-end', 'true'], *args, **kwargs)
controller.traci.start = start_gui
original_evaluate = controller.AgenPengamat.evaluate
counts = {'pengamat': 0, 'katup': 0, 'rute': 0}
control = {'mode': 'DISABLED' if mode == 'baseline' else 'NORMAL', 'rerouted': 0}
for name, cls, method in [('katup', controller.AgenKatup, 'apply_control'), ('rute', controller.AgenRute, 'guide_traffic')]:
    original = getattr(cls, method)
    def counted(self, *args, _name=name, _original=original, **kwargs):
        counts[_name] += 1
        result = _original(self, *args, **kwargs)
        if _name == 'katup': control['mode'] = self.mode
        if _name == 'rute': control['rerouted'] = self.reroute_counter
        return result
    setattr(cls, method, counted)

def evaluate(self):
    metrics = original_evaluate(self)
    counts['pengamat'] += 1
    vehicles = controller.traci.vehicle.getIDList()
    sample = vehicles[0] if vehicles else None
    data = dict(scenario=mode, simulation_time=controller.traci.simulation.getTime(),
                vehicles=len(vehicles), sample_vehicle=sample,
                sample_position=controller.traci.vehicle.getPosition(sample) if sample else None,
                calls=counts.copy(), control=control.copy(), metrics=metrics, updated=time.time())
    temporary = state_file.with_suffix('.tmp')
    temporary.write_text(json.dumps(data))
    temporary.replace(state_file)
    return metrics
controller.AgenPengamat.evaluate = evaluate
print(f'Scenario={mode}; research controller={ROOT / "katup_controller.py"}', flush=True)
controller.run_simulation(enable_katup=mode == 'katup', use_gui=True)
