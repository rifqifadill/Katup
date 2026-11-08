"""Run one KATUP scenario and publish live telemetry for the web dashboard."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import statistics
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "progress_tahapan/05_visual_urban_enhancements"
spec = importlib.util.spec_from_file_location("katup_research", ROOT / "katup_controller.py")
controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(controller)
os.chdir(SIM_DIR)

mode = os.environ.get("KATUP_SCENARIO") or (os.sys.argv[1] if len(os.sys.argv) > 1 else "katup")
if mode not in ("baseline", "katup"):
    raise SystemExit("Unknown scenario")

state_file = Path(os.environ["KATUP_TELEMETRY"])
state_file.parent.mkdir(parents=True, exist_ok=True)
runs_dir = state_file.parent / "runs"
runs_dir.mkdir(parents=True, exist_ok=True)
seed = int(os.environ.get("KATUP_SEED", "42"))
delay = int(os.environ.get("KATUP_DELAY", "1000"))
use_gui = os.environ.get("KATUP_USE_GUI", "1") not in {"0", "false", "no"}
tripinfo_file = runs_dir / f"{mode}-seed-{seed}.tripinfo.xml"
original_start = controller.traci.start
original_step = controller.traci.simulationStep


def paced_step(*args, **kwargs):
    started = time.monotonic()
    result = original_step(*args, **kwargs)
    if not use_gui:
        time.sleep(max(0, delay / 1000 - (time.monotonic() - started)))
    return result


controller.traci.simulationStep = paced_step

counts = {"pengamat": 0, "katup": 0, "rute": 0}
control = {"mode": "DISABLED" if mode == "baseline" else "NORMAL", "rerouted": 0}
series: list[dict] = []
events: list[dict] = []
last_mode = control["mode"]
last_rerouted = 0
last_data: dict = {}
last_vehicle_sample: list[dict] = []


def start_sumo(cmd, *args, **kwargs):
    options = [
        "--delay", str(delay),
        "--seed", str(seed),
        "--quit-on-end", "true",
        "--tripinfo-output", str(tripinfo_file),
    ]
    if not use_gui:
        options.extend(["--no-step-log", "true"])
    return original_start(cmd + options, *args, **kwargs)


controller.traci.start = start_sumo
original_evaluate = controller.AgenPengamat.evaluate
original_apply = controller.AgenKatup.apply_control
original_route = controller.AgenRute.guide_traffic


def edge_snapshot(edge_id: str) -> dict:
    traci = controller.traci
    return {
        "vehicles": traci.edge.getLastStepVehicleNumber(edge_id),
        "halting": traci.edge.getLastStepHaltingNumber(edge_id),
        "speed_kmh": round(traci.edge.getLastStepMeanSpeed(edge_id) * 3.6, 2),
        "occupancy_pct": round(traci.edge.getLastStepOccupancy(edge_id) * 100, 2),
    }


def vehicle_snapshot(limit: int = 80) -> list[dict]:
    traci = controller.traci
    result = []
    for vehicle_id in traci.vehicle.getIDList()[:limit]:
        try:
            x, y = traci.vehicle.getPosition(vehicle_id)
            route = traci.vehicle.getRoute(vehicle_id)
            result.append({
                "id": vehicle_id,
                "x": round(x, 1),
                "y": round(y, 1),
                "edge": traci.vehicle.getRoadID(vehicle_id),
                "speed": round(traci.vehicle.getSpeed(vehicle_id) * 3.6, 1),
                "rerouted": len(route) > 1 and route[1] == "edge_J2N",
            })
        except Exception:
            continue
    return result


def write_state(data: dict) -> None:
    temporary = state_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, separators=(",", ":")))
    temporary.replace(state_file)


def record_event(kind: str, message: str, step: int, **extra) -> None:
    events.append({"time": step, "kind": kind, "message": message, **extra})
    del events[:-30]


def make_state(metrics: dict, step: int) -> dict:
    global last_vehicle_sample
    traci = controller.traci
    downstream = edge_snapshot("edge_pre_bottle")
    upstream = edge_snapshot("edge_W2J")
    bottleneck = edge_snapshot("edge_bottleneck")
    bypass = {
        "vehicles": sum(edge_snapshot(e)["vehicles"] for e in ("edge_J2N", "edge_alt_1", "edge_alt_2")),
        "halting": sum(edge_snapshot(e)["halting"] for e in ("edge_J2N", "edge_alt_1", "edge_alt_2")),
    }
    phase = {
        "index": traci.trafficlight.getPhase(controller.TLS_ID),
        "duration": round(traci.trafficlight.getPhaseDuration(controller.TLS_ID), 2),
        "next_switch": round(traci.trafficlight.getNextSwitch(controller.TLS_ID), 2),
    }
    sample = last_vehicle_sample[0] if last_vehicle_sample else None
    state = {
        "schema": 2,
        "scenario": mode,
        "seed": seed,
        "running": True,
        "finished": False,
        "gui_delay_ms": delay,
        "simulation_time": traci.simulation.getTime(),
        "step": step,
        "vehicles": len(traci.vehicle.getIDList()),
        "sample_vehicle": sample["id"] if sample else None,
        "sample_position": [sample["x"], sample["y"]] if sample else None,
        "departed": traci.simulation.getDepartedNumber(),
        "arrived": traci.simulation.getArrivedNumber(),
        "metrics": {
            "observer": metrics,
            "downstream": downstream,
            "upstream": upstream,
            "bottleneck": bottleneck,
            "bypass": bypass,
        },
        "phase": phase,
        "calls": counts.copy(),
        "control": control.copy(),
        "events": events[-30:],
        "vehicles_sample": last_vehicle_sample,
        "series": series[-360:],
        "updated": time.time(),
    }
    return state


def evaluate(self):
    global last_data, last_mode, last_rerouted, last_vehicle_sample
    metrics = original_evaluate(self)
    counts["pengamat"] += 1
    step = int(controller.traci.simulation.getTime())
    if step % 5 == 0 or step <= 2:
        series.append({
            "time": step,
            "downstream": metrics["veh_count"],
            "upstream": controller.traci.edge.getLastStepVehicleNumber("edge_W2J"),
            "speed": round(metrics["mean_speed_kmh"], 2),
            "bottleneck": controller.traci.edge.getLastStepVehicleNumber("edge_bottleneck"),
            "rerouted": control["rerouted"],
            "mode": control["mode"],
        })
    if step % 2 == 0 or step <= 2:
        last_vehicle_sample = vehicle_snapshot()
    last_data = make_state(metrics, step)
    write_state(last_data)
    return metrics


def apply_control(self, *args, **kwargs):
    global last_mode
    counts["katup"] += 1
    result = original_apply(self, *args, **kwargs)
    control["mode"] = self.mode
    if self.mode != last_mode:
        record_event(
            "control",
            "Valve aktif" if self.mode == "KATUP_ACTIVE" else "Kembali normal",
            int(controller.traci.simulation.getTime()),
            mode=self.mode,
        )
        last_mode = self.mode
    return result


def guide_traffic(self, *args, **kwargs):
    global last_rerouted
    counts["rute"] += 1
    result = original_route(self, *args, **kwargs)
    control["rerouted"] = self.reroute_counter
    if self.reroute_counter > last_rerouted:
        record_event(
            "route",
            f"{self.reroute_counter - last_rerouted} kendaraan diarahkan ke bypass",
            int(controller.traci.simulation.getTime()),
            total=self.reroute_counter,
        )
        last_rerouted = self.reroute_counter
    return result


controller.AgenPengamat.evaluate = evaluate
controller.AgenKatup.apply_control = apply_control
controller.AgenRute.guide_traffic = guide_traffic


def trip_summary() -> dict:
    if not tripinfo_file.exists():
        return {"completed_trips": 0}
    try:
        root = ET.parse(tripinfo_file).getroot()
        trips = list(root.findall("tripinfo"))
        summary = {"completed_trips": len(trips)}
        for key in ("duration", "waitingTime", "timeLoss", "routeLength"):
            values = [float(t.attrib[key]) for t in trips if key in t.attrib]
            if values:
                summary[f"avg_{key}"] = round(statistics.mean(values), 2)
        return summary
    except (OSError, ET.ParseError, ValueError):
        return {"completed_trips": 0}


try:
    print(f"Scenario={mode}; seed={seed}; dashboard controller", flush=True)
    controller.run_simulation(enable_katup=mode == "katup", use_gui=use_gui)
    final = dict(last_data)
    final.update({"running": False, "finished": True, "simulation_time": 1800, "updated": time.time()})
    final["summary"] = trip_summary()
    write_state(final)
    (runs_dir / f"{mode}.json").write_text(json.dumps({
        "scenario": mode,
        "seed": seed,
        "summary": final["summary"],
        "series": series,
        "events": events,
        "final": final,
    }, separators=(",", ":")))
except Exception as exc:
    error = dict(last_data)
    error.update({"running": False, "finished": False, "error": str(exc), "traceback": traceback.format_exc(), "updated": time.time()})
    write_state(error)
    raise
