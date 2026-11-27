"""KATUP: queue-aware signal control and capacity-aware early route guidance."""
from collections import deque
import logging
import os
from pathlib import Path
import sys

if 'SUMO_HOME' in os.environ:
    sys.path.append(str(Path(os.environ['SUMO_HOME']) / 'tools'))
import traci
import traci.constants as tc
from katup_scenario import build_scenario, DURATION
from katup_core.scenarios import build_case, get_profile
from katup_core.strategy import PROFILES, Strategy, Supervisor

TLS_ID = 'titik_urai'
EDGE_PRE_BOTTLENECK = 'edge_pre_bottle'
EDGE_INBOUND_WEST = 'edge_W2J'
EDGE_DECISION = 'edge_W_far2W'
BYPASS_EDGES = ['edge_W2J', 'edge_J2N', 'edge_alt_1', 'edge_alt_2', 'edge_post_merge']
LOG = logging.getLogger(__name__)
PROFILE = get_profile()


def get_phase_spent_duration(tls_id):
    getter = getattr(traci.trafficlight, 'getSpentDuration', None)
    if getter is not None:
        return getter(tls_id)
    return traci.trafficlight.getPhaseDuration(tls_id) - (
        traci.trafficlight.getNextSwitch(tls_id) - traci.simulation.getTime())


def queue_length(prefix):
    sensors = PROFILE.get('detector_groups', {}).get(prefix, [prefix])
    return sum(max((traci.lanearea.getJamLengthMeters(f'{sensor}_{lane}') for lane in range(traci.edge.getLaneNumber(PROFILE['detectors'][sensor]))), default=0) for sensor in sensors)


def pre_edges():
    return PROFILE.get('pre_edges', [PROFILE['pre']])


def monitored_length():
    return sum(traci.lane.getLength(edge + '_0') for edge in pre_edges())


def approach_halting(edges):
    monitored = {part for edge in edges for part in PROFILE.get('approach_edges', {}).get(edge, [edge])}
    return sum(traci.edge.getLastStepHaltingNumber(edge) for edge in monitored)


def edge_metrics(edges):
    counts = {edge: traci.edge.getLastStepVehicleNumber(edge) for edge in edges}
    lengths = {edge: sum(traci.lane.getLength(f'{edge}_{lane}') for lane in range(traci.edge.getLaneNumber(edge))) for edge in edges}
    count = sum(counts.values())
    total_length = sum(lengths.values())
    speed = sum(traci.edge.getLastStepMeanSpeed(edge) * vehicles for edge, vehicles in counts.items()) / count if count else traci.edge.getLastStepMeanSpeed(edges[0])
    return {'vehicles': count, 'halting': sum(traci.edge.getLastStepHaltingNumber(edge) for edge in edges), 'speed_kmh': speed * 3.6, 'occupancy_pct': sum(traci.edge.getLastStepOccupancy(edge) * length for edge, length in lengths.items()) / total_length}


class AgenPengamat:
    """Measure physical queue lengths, upstream pressure and junction blockage."""
    def __init__(self, edge_id):
        self.edge_id = edge_id
        self.edges = pre_edges() if edge_id == PROFILE['pre'] else [edge_id]
        self.length = sum(traci.lane.getLength(edge + '_0') for edge in self.edges)
        self.capacity = sum(traci.lane.getLength(edge + f'_{i}') for edge in self.edges for i in range(traci.edge.getLaneNumber(edge))) / 7.5
        self.safe_seconds = 0
        self.metrics = {}
        self.junction_id = PROFILE.get('junction', TLS_ID)
        traci.junction.subscribeContext(self.junction_id, tc.CMD_GET_VEHICLE_VARIABLE, 30,
            [tc.VAR_SPEED, tc.VAR_ROAD_ID])

    def evaluate(self):
        snapshot = edge_metrics(self.edges)
        count = snapshot['vehicles']
        jam = queue_length('pre')
        west = queue_length('west')
        farwest = queue_length('farwest')
        ratio = jam / self.length
        safe = ratio < 0.2 and west < 70
        self.safe_seconds = self.safe_seconds + 1 if safe else 0
        nearby = traci.junction.getContextSubscriptionResults(self.junction_id) or {}
        stopped_in_box = sum(
            car[tc.VAR_SPEED] < 0.1 and car[tc.VAR_ROAD_ID].startswith(':' + self.junction_id)
            for car in nearby.values())
        self.metrics = {
            'veh_count': count,
            'halting': snapshot['halting'],
            'occupancy': snapshot['occupancy_pct'],
            'mean_speed_kmh': snapshot['speed_kmh'],
            'density_ratio': min(100, count / self.capacity * 100),
            'queue_m': jam, 'queue_ratio': ratio,
            'upstream_queue_m': west, 'far_upstream_queue_m': farwest,
            'cross_queue_m': max(queue_length(prefix) for prefix in PROFILE.get('cross_detectors', ('north', 'south'))),
            'junction_stopped': stopped_in_box,
            'spillback': ratio >= 0.9,
            'is_high_risk': ratio >= 0.55 or west >= 180,
            'can_return_to_normal': self.safe_seconds >= 15,
        }
        return self.metrics


class AgenKatup:
    """Serve queued approaches; preserve yellow/all-red and minimum green."""
    def __init__(self, tls_id):
        self.tls_id = tls_id
        self.mode = 'ADAPTIVE'
        self.last_phase = -1
        self.phase_started = 0
        self.last_action = 'Memantau antrean dua arah'
        self.strategy = Strategy()

    def apply_control(self, is_high_risk, can_return_to_normal):
        if is_high_risk:
            self.mode = 'KATUP_ACTIVE'
        elif can_return_to_normal:
            self.mode = 'ADAPTIVE'
        phase = traci.trafficlight.getPhase(self.tls_id)
        now = traci.simulation.getTime()
        if phase != self.last_phase:
            self.phase_started = now
            self.last_phase = phase
        elapsed = now - self.phase_started
        west = approach_halting([PROFILE['west']])
        served = [edge for edge in PROFILE['north'] + PROFILE['south'] if edge != PROFILE['west']]
        if phase in PROFILE['phases']['cross']:
            served = PROFILE['phases'].get('served', {}).get(str(phase), served)
        cross = approach_halting(served)
        limit = PROFILES[self.strategy.profile]['green_limit']
        if phase in PROFILE['phases']['cross'] and elapsed >= 12 and (cross == 0 or (elapsed >= 30 and west > 0)):
            traci.trafficlight.setPhase(self.tls_id, phase + 1)
            self.last_action = 'Melayani arus utama setelah antrean silang terlayani'
        elif phase in PROFILE['phases']['main'] and elapsed >= 10:
            downstream_full = queue_length('pre') > 0.75 * monitored_length()
            if west == 0 or (elapsed >= limit and cross > 0) or downstream_full:
                traci.trafficlight.setPhase(self.tls_id, phase + 1)
                self.last_action = 'Menahan arus masuk pekerjaan jalan' if downstream_full else 'Melayani arus silang'


class AgenRute:
    """Select detours before the upstream junction, preserving the destination."""
    def __init__(self, inbound_edge=EDGE_DECISION, bypass_route=None):
        self.inbound_edge = PROFILE['decision'] if inbound_edge == 'edge_W_far2W' else inbound_edge
        self.paths = [list(path) for path in PROFILE['paths']]
        self.route_names = list(PROFILE['route_names'])
        if inbound_edge != EDGE_DECISION and bypass_route:
            self.paths = [list(bypass_route)]
            self.route_names = ['Bypass']
        self.main = list(PROFILE['main'])
        self.strategy = Strategy()
        self.seen = set()
        self.credit = 0.0
        self.reroute_counter = 0
        self.failed_reroutes = 0
        self.reservations = deque()
        self.next_refresh = 0
        self.costs = []
        self.available = []
        self.route_totals = {name: 0 for name in self.route_names}
        self.route_mode = 'STANDBY'
        self.target_fraction = 0.7
        self.main_cost = 0.0
        self.edge_capacity = {}
        for path in self.paths:
            for edge in path[1:]:
                lanes = traci.edge.getLaneNumber(edge)
                self.edge_capacity[edge] = sum(traci.lane.getLength(f'{edge}_{i}') for i in range(lanes)) / 7.5

    def refresh_routes(self, now):
        self.costs = [sum(min(900, traci.edge.getTraveltime(edge)) for edge in path[1:]) for path in self.paths]
        self.main_cost = sum(min(900, traci.edge.getTraveltime(edge)) for edge in self.main)
        self.available = [all(traci.edge.getLastStepVehicleNumber(edge) < self.edge_capacity[edge] * 0.8
                              for edge in path[1:]) for path in self.paths]
        self.next_refresh = now + 5

    def guide_traffic(self, is_active):
        if not is_active:
            self.route_mode = 'DISABLED'
            return
        now = traci.simulation.getTime()
        if now >= self.next_refresh:
            self.refresh_routes(now)
        while self.reservations and self.reservations[0][0] < now - 45:
            self.reservations.popleft()
        counts = [sum(route == i for _, route in self.reservations) for i in range(len(self.paths))]
        self.route_mode = 'STANDBY'
        for vehicle in traci.edge.getLastStepVehicleIDs(self.inbound_edge):
            if vehicle in self.seen:
                continue
            original = traci.vehicle.getRoute(vehicle)
            if PROFILE['bottleneck'] not in original:
                continue
            self.seen.add(vehicle)
            eligible = [i for i, path in enumerate(self.paths) if self.available[i] and original[-1] in path]
            if not eligible:
                continue
            scores = [cost + 3 * count - (5 if self.route_names[i] == self.strategy.route_bias else 0) for i, (cost, count) in enumerate(zip(self.costs, counts))]
            choice = min(eligible, key=lambda i: scores[i])
            if self.costs[choice] + 3 * counts[choice] > self.main_cost + 30:
                continue
            count = sum(traci.edge.getLastStepVehicleNumber(edge) for edge in pre_edges())
            self.target_fraction = 0.70 if count < 8 else 0.82 if count < 16 else 0.90
            self.target_fraction = min(0.90, self.target_fraction + PROFILES[self.strategy.profile]['reroute_delta'])
            self.credit += self.target_fraction
            self.route_mode = 'ACTIVE'
            if self.credit < 1:
                continue
            path = self.paths[choice]
            path = path[:path.index(original[-1]) + 1]
            try:
                traci.vehicle.setRoute(vehicle, path)
                traci.vehicle.setColor(vehicle, (0, 255, 0, 255))
            except traci.exceptions.TraCIException:
                self.failed_reroutes += 1
                LOG.exception('Pengalihan gagal untuk %s', vehicle)
                continue
            self.credit -= 1
            self.reroute_counter += 1
            self.route_totals[self.route_names[choice]] += 1
            counts[choice] += 1
            self.reservations.append((now, choice))


class RunMetrics:
    """Include unfinished vehicles and insertion queues in system-wide metrics."""
    def __init__(self):
        self.total_vehicle_seconds = 0
        self.pending_vehicle_seconds = 0
        self.spillback_seconds = 0
        self.junction_stopped_seconds = 0
        self.junction_blocked_seconds = 0
        self.blocked_streak = 0
        self.max_queue_m = 0
        self.max_upstream_queue_m = 0
        self.arrived = 0
        self.departed = 0
        self.pending = 0
        self.running = 0
        self.collisions = 0
        self.teleports = 0

    def update(self, metrics):
        self.pending = len(traci.simulation.getPendingVehicles())
        self.running = traci.vehicle.getIDCount()
        self.total_vehicle_seconds += self.running + self.pending
        self.pending_vehicle_seconds += self.pending
        self.arrived += traci.simulation.getArrivedNumber()
        self.departed += traci.simulation.getDepartedNumber()
        self.spillback_seconds += int(metrics['spillback'])
        stopped = metrics['junction_stopped'] > 0
        self.junction_stopped_seconds += int(stopped)
        self.blocked_streak = self.blocked_streak + 1 if stopped else 0
        if self.blocked_streak == 5:
            self.junction_blocked_seconds += 5
        elif self.blocked_streak > 5:
            self.junction_blocked_seconds += 1
        self.max_queue_m = max(self.max_queue_m, metrics['queue_m'])
        self.max_upstream_queue_m = max(self.max_upstream_queue_m, metrics['upstream_queue_m'])
        self.collisions += traci.simulation.getCollidingVehiclesNumber()
        self.teleports += traci.simulation.getStartingTeleportNumber()

    def summary(self):
        return {
            'total_vehicle_hours': round(self.total_vehicle_seconds / 3600, 3),
            'pending_vehicle_hours': round(self.pending_vehicle_seconds / 3600, 3),
            'spillback_seconds': self.spillback_seconds,
            'junction_stopped_seconds': self.junction_stopped_seconds,
            'junction_blocked_seconds': self.junction_blocked_seconds,
            'max_queue_m': round(self.max_queue_m, 1),
            'max_upstream_queue_m': round(self.max_upstream_queue_m, 1),
            'arrived': self.arrived, 'departed': self.departed,
            'pending': self.pending, 'running': self.running,
            'collisions': self.collisions, 'teleports': self.teleports,
        }


def run_simulation(enable_katup=True, use_gui=True, on_step=None, corridor=None, demand='peak', mode=None, run_id=None, audit_path=None):
    global PROFILE, TLS_ID, EDGE_PRE_BOTTLENECK, EDGE_INBOUND_WEST, EDGE_DECISION
    if corridor:
        config, case = build_case(corridor, demand)
        PROFILE = case['profile']
        duration = case['duration']
    else:
        config = build_scenario()
        PROFILE = get_profile()
        duration = DURATION
    TLS_ID, EDGE_PRE_BOTTLENECK, EDGE_INBOUND_WEST, EDGE_DECISION = (PROFILE[key] for key in ('tls', 'pre', 'west', 'decision'))
    mode = mode or ('katup' if enable_katup else 'baseline')
    if mode not in ('baseline', 'katup', 'hybrid'):
        raise ValueError('Mode tidak dikenal')
    enable_katup = mode != 'baseline'
    supervisor = Supervisor(run_id or f'{mode}-{os.getpid()}', audit_path=audit_path) if mode == 'hybrid' else None
    command = ['sumo-gui' if use_gui else 'sumo', '-c', str(config), '--start', 'true']
    traci.start(command)
    try:
        observer = AgenPengamat(EDGE_PRE_BOTTLENECK)
        valve = AgenKatup(TLS_ID)
        route = AgenRute()
        route.supervisor = supervisor
        recorder = RunMetrics()
        for step in range(1, duration + 1):
            traci.simulationStep()
            metrics = observer.evaluate()
            if enable_katup:
                if supervisor:
                    if step >= route.next_refresh:
                        route.refresh_routes(step)
                    routes = [{'name': name, 'cost_seconds': round(cost, 1), 'available': available} for name, cost, available in zip(route.route_names, route.costs, route.available)]
                    strategy = supervisor.update(step, metrics, routes)
                    route.strategy = strategy
                    valve.strategy = strategy
                valve.apply_control(metrics['is_high_risk'], metrics['can_return_to_normal'])
                route.guide_traffic(True)
            recorder.update(metrics)
            if on_step is not None:
                on_step(step, metrics, valve, route, recorder)
            if step % 60 == 0:
                print(f'{step}s | hilir {metrics["queue_m"]:.0f}m | hulu {metrics["upstream_queue_m"]:.0f}m | tiba {recorder.arrived} | alih {route.reroute_counter}', flush=True)
        return recorder.summary()
    finally:
        if supervisor:
            supervisor.close()
        traci.close()


if __name__ == '__main__':
    args = {arg.lower() for arg in sys.argv[1:]}
    run_simulation(enable_katup=not args.intersection({'baseline', 'no-katup', '0'}),
                   use_gui=not args.intersection({'--nogui', '-nogui'}))
