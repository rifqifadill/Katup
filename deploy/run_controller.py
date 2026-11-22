"""Run one KATUP scenario and publish live telemetry for the web dashboard."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from katup_scenario import CASE_DIR, build_scenario, case_metadata
build_scenario()
CASE = case_metadata()
SIM_DIR = CASE_DIR
spec = importlib.util.spec_from_file_location("katup_research", ROOT / "katup_controller.py")
controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(controller)
import traci.constants as tc
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
tripinfo_file = runs_dir / f"{mode}-seed-{seed}-{CASE['signature']}.tripinfo.xml"
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


def edge_snapshot(edge_id: str) -> dict:
    traci = controller.traci
    return {
        "vehicles": traci.edge.getLastStepVehicleNumber(edge_id),
        "halting": traci.edge.getLastStepHaltingNumber(edge_id),
        "speed_kmh": round(traci.edge.getLastStepMeanSpeed(edge_id) * 3.6, 2) if traci.edge.getLastStepVehicleNumber(edge_id) else None,
        "occupancy_pct": round(traci.edge.getLastStepOccupancy(edge_id), 2),
    }


vehicle_metadata = {}


def vehicle_snapshot() -> list[dict]:
    """Read positions from SUMO subscriptions: one batch instead of 6 calls/car."""
    traci = controller.traci
    variables = (tc.VAR_POSITION, tc.VAR_ANGLE, tc.VAR_SPEED, tc.VAR_ROAD_ID, tc.VAR_COLOR)
    ids = traci.vehicle.getIDList()
    active = set(ids)
    for stale in vehicle_metadata.keys() - active:
        del vehicle_metadata[stale]
    for vid in ids:
        if vid not in vehicle_metadata:
            traci.vehicle.subscribe(vid, variables)
            vehicle_metadata[vid] = {
                "length": round(traci.vehicle.getLength(vid), 2),
                "width": round(traci.vehicle.getWidth(vid), 2),
                "kind": traci.vehicle.getVehicleClass(vid),
            }
    result = []
    subscribed = traci.vehicle.getAllSubscriptionResults()
    for vid in ids:
        data = subscribed.get(vid)
        if not data or tc.VAR_POSITION not in data:
            continue
        x, y = data[tc.VAR_POSITION]
        color = data.get(tc.VAR_COLOR, (220, 230, 240, 255))
        result.append({
            "id": vid, "x": round(x, 2), "y": round(y, 2),
            "angle": round(data[tc.VAR_ANGLE], 1),
            "edge": data[tc.VAR_ROAD_ID],
            "speed": round(data[tc.VAR_SPEED] * 3.6, 1),
            "rerouted": color[0] == 0 and color[1] == 255 and color[2] == 0,
            **vehicle_metadata[vid],
        })
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
        "schema": 4,
        "case": CASE,
        "run_id": f"{mode}-{os.getpid()}",
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


def publish_step(step, metrics, valve, route, recorder):
    global last_data, last_mode, last_rerouted, last_vehicle_sample
    counts["pengamat"] = step
    counts["katup"] = step if mode == "katup" else 0
    counts["rute"] = step if mode == "katup" else 0
    control.update({
        "mode": valve.mode if mode == "katup" else "DISABLED",
        "rerouted": route.reroute_counter,
        "route_mode": route.route_mode if mode == "katup" else "DISABLED",
        "route_totals": route.route_totals,
        "target_fraction": route.target_fraction,
        "last_action": valve.last_action if mode == "katup" else "Lampu tetap 40 / 3 / 47 detik",
        "failed_reroutes": route.failed_reroutes,
    })
    if control["mode"] != last_mode:
        record_event("control", "Proteksi spillback aktif" if valve.mode == "KATUP_ACTIVE" else "Lampu adaptif mengikuti antrean", step)
        last_mode = control["mode"]
    if route.reroute_counter > last_rerouted:
        record_event("route", f"{route.reroute_counter - last_rerouted} kendaraan menerima rute alternatif", step, total=route.reroute_counter)
        last_rerouted = route.reroute_counter
    if metrics["spillback"] and not last_data.get("metrics", {}).get("observer", {}).get("spillback"):
        record_event("spillback", "Antrean galian mencapai 90% ruas menuju simpang", step)
    if step % 5 == 0 or step <= 2:
        series.append({
            "time": step, "downstream": metrics["veh_count"],
            "upstream": controller.traci.edge.getLastStepVehicleNumber("edge_W2J"),
            "speed": round(metrics["mean_speed_kmh"], 2),
            "queue_m": round(metrics["queue_m"], 1),
            "upstream_queue_m": round(metrics["upstream_queue_m"], 1),
            "bottleneck": controller.traci.edge.getLastStepVehicleNumber("edge_bottleneck"),
            "rerouted": control["rerouted"], "mode": control["mode"],
        })
    last_vehicle_sample = vehicle_snapshot()
    last_data = make_state(metrics, step)
    last_data["system"] = recorder.summary()
    last_data["sumo_version"] = controller.traci.getVersion()[1] if step == 1 else sumo_version[0]
    if step == 1:
        sumo_version[0] = last_data["sumo_version"]
    write_state(last_data)


sumo_version = [None]


def trip_summary() -> dict:
    if not tripinfo_file.exists():
        return {"completed_trips": 0}
    try:
        root = ET.parse(tripinfo_file).getroot()
        trips = list(root.findall("tripinfo"))
        summary = {"completed_trips": len(trips)}
        for key in ("duration", "waitingTime", "timeLoss", "routeLength", "departDelay"):
            values = [float(t.attrib[key]) for t in trips if key in t.attrib]
            if values:
                summary[f"avg_{key}"] = round(statistics.mean(values), 2)
        return summary
    except (OSError, ET.ParseError, ValueError):
        return {"completed_trips": 0}


try:
    print(f"Scenario={mode}; seed={seed}; dashboard controller", flush=True)
    system_summary = controller.run_simulation(enable_katup=mode == "katup", use_gui=use_gui, on_step=publish_step)
    final = dict(last_data)
    final.update({"running": False, "finished": True, "simulation_time": 1800, "updated": time.time()})
    final["summary"] = {**trip_summary(), **system_summary}
    write_state(final)
    saved = {
        "scenario": mode,
        "seed": seed,
        "case": CASE,
        "sumo_version": sumo_version[0],
        "summary": final["summary"],
        "series": series,
        "events": events,
        "final": final,
    }
    output = runs_dir / f"{mode}.json"
    if output.exists():
        archive = runs_dir / f"{mode}-previous-{time.time_ns()}.json"
        output.replace(archive)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(saved, separators=(",", ":")))
    temporary.replace(output)
except Exception as exc:
    error = dict(last_data)
    error.update({"running": False, "finished": False, "error": str(exc), "traceback": traceback.format_exc(), "updated": time.time()})
    write_state(error)
    raise
