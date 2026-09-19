import math
import argparse
import json
import time
import os
from pathlib import Path
from .paths import DEFAULT_LOG_DIR
import cv2
from .drone_sim import DroneState, PackageState, BASE, Drone2DEnvironment


from .physics import *
from .charging import *
from .assignment_costs.features import *
from .assignment_costs.v1_cost import *
from .assignment_costs.v2_cost import *

from . import fsm
from . import assignment
from .wind import *
from .telemetry import evaluate_mission_state


def should_create_hard_package(sim_time):
    # Harder workload: faster arrivals (every 10s)
    return sim_time > 0 and (sim_time % 10.0) < 0.001

def generate_hard_package(package_id, sim_time):
    # More dispersed drop points, heavy weights, shorter deadlines
    dx = [300, -400, 500, -200, 600, -500, 250, -350, 450, -600]
    dy = [400, 300, -500, -200, 200, 600, -300, -400, 150, -50]
    idx = package_id % 10
    x = BASE[0] + dx[idx]
    y = BASE[1] + dy[idx]
    # Heavy and light
    weight = 0.5 if (package_id % 2 == 0) else 2.5 
    # Short deadline (between 60s to 120s depending on distance)
    # The absolute distance is up to 850px (~85 meters). Round trip ~170m.
    # At 8.4m/s, flight takes ~20 seconds.
    deadline = sim_time + 60.0
    
    return PackageState(
        id=package_id,
        x=float(x),
        y=float(y),
        weight=weight,
        request_time=sim_time,
        deadline=deadline,
        assigned_drone=None,
        delivered=False
    )

def update_drone(drone, packages, dt, charging_pads, sim_time=0.0, wind_events=None):
    wind_events = [] if wind_events is None else wind_events

    remaining_dt = dt

    while remaining_dt > 0:

        speed_meters = calculate_speed(drone.payload)
        speed_pixels = meters_to_pixels(speed_meters)

        if drone.status == "DELIVERY":
            if drone.current_package is None:
                return
            package = packages[drone.current_package]
            
            telemetry = evaluate_mission_state(drone, package, sim_time, wind_events)
            if not hasattr(package, 'telemetry_history'):
                package.telemetry_history = []
            package.telemetry_history.append(telemetry)
            
            if telemetry["status"] == "ABORT":
                fsm.abort_mission(drone, package, sim_time, telemetry["reason"])
                continue

            distance_moved, actual_time, reached = move_towards(
                drone,
                drone.target,
                speed_pixels,
                remaining_dt,
                sim_time,
                wind_events
            )
            
            drone.total_distance += distance_moved
            drone.total_flight_time += actual_time

            consume_battery(drone, actual_time)

            remaining_dt -= actual_time

            if drone.battery <= 0:
                drone.battery = 0.0
                drone.status = "FAILED"
                drone.target = None
                return

            if reached:
                fsm.complete_delivery(drone, package, sim_time, dt, remaining_dt)
                continue

        elif drone.status == "RETURNING":

            distance_moved, actual_time, reached = move_towards(
                drone,
                drone.target,
                speed_pixels,
                remaining_dt,
                sim_time,
                wind_events
            )
            
            drone.total_distance += distance_moved
            drone.total_flight_time += actual_time

            consume_battery(drone, actual_time)

            remaining_dt -= actual_time

            if drone.battery <= 0:
                drone.battery = 0.0
                drone.status = "FAILED"
                drone.target = None
                return

            if reached:
                fsm.return_to_base(drone, packages, sim_time)
                continue

        elif drone.status == "CHARGING":
            update_charging(drone, remaining_dt, charging_pads)
            return

        elif drone.status == "WAITING_FOR_CHARGE":
            drone.total_charge_wait_time += remaining_dt
            if start_charging(drone, charging_pads):
                return
            return

        else:
            return











def quarantine_invalid_drones(drones, packages, charging_pads, sim_time):
    for drone in drones.values():
        if drone.status == "QUARANTINED":
            continue
        invalid = False
        reason = ""
        if not math.isfinite(drone.battery) or not math.isfinite(drone.x) or not math.isfinite(drone.y):
            invalid, reason = True, "NaN in telemetry"
        elif drone.battery < -1e-6 or drone.battery > drone.battery_capacity + 1e-6:
            invalid, reason = True, f"Battery out of bounds: {drone.battery}"
            
        if invalid:
            drone.status = "QUARANTINED"
            if drone.current_package is not None:
                pkg = packages[drone.current_package]
                pkg.status = "PENDING"
                pkg.assigned_drone = None
                if not hasattr(pkg, 'decision_history'):
                    pkg.decision_history = []
                pkg.decision_history.append({
                    "sim_time": sim_time,
                    "action": "ABORTED_DUE_TO_QUARANTINE",
                    "reason": f"Drone quarantined: {reason}"
                })
                drone.current_package = None
            if drone.charging_pad is not None:
                charging_pads[drone.charging_pad] = None
                drone.charging_pad = None

def validate_simulation(drones, charging_pads):
    for drone in drones.values():
        if drone.status == "QUARANTINED":
            continue
        assert drone.battery >= -1e-6, f"Drone {drone.id} battery negative: {drone.battery}"
        assert drone.battery <= drone.battery_capacity + 1e-6, f"Drone {drone.id} battery exceeds capacity"

        if drone.status == "CHARGING":
            assert drone.charging_pad is not None, f"Drone {drone.id} charging but no pad"
            assert charging_pads[drone.charging_pad] == drone.id, f"Pad {drone.charging_pad} doesn't match drone {drone.id}"
        else:
            assert drone.charging_pad is None, f"Drone {drone.id} not charging but has pad {drone.charging_pad}"

    for pad_id, drone_id in charging_pads.items():
        if drone_id is not None:
            assert drone_id in drones
            drone = drones[drone_id]
            assert drone.status == "CHARGING", f"Pad {pad_id} has drone {drone_id} but status is {drone.status}"
            assert drone.charging_pad == pad_id, f"Drone {drone_id} on pad {pad_id} thinks it's on {drone.charging_pad}"

def get_idle_drone(drones):
    for drone in drones.values():
        if drone.status == "IDLE":
            return drone
    return None

def update_package_outcomes(drones, packages, sim_time):
    """Only unassigned jobs expire; an airborne package keeps its physical owner."""
    for package in packages.values():
        if package.status != "PENDING" or package.assigned_drone is not None or package.delivered:
            continue
        if package.request_time > sim_time:
            continue
        values = (package.x, package.y, package.weight, package.deadline, package.request_time)
        reason = None
        if not all(math.isfinite(v) for v in values) or package.weight < 0:
            reason = "Invalid request"
        elif package.weight > 2.5:
            reason = "Payload exceeds fleet limit"
        elif sim_time > package.deadline:
            package.status = "EXPIRED"
            reason = "Deadline passed while waiting"
        elif drones:
            # Packages are collected at the base. Ignore commitments here:
            # reject only if even an immediately available, fully charged drone cannot serve it.
            ideal = DroneState(id=0, x=float(BASE[0]), y=float(BASE[1]))
            if sim_time + calculate_delivery_time(ideal, package) > package.deadline + 1e-9:
                reason = "Even immediate departure cannot meet deadline"
            elif calculate_required_battery(ideal, package) > max(d.battery_capacity for d in drones.values()):
                reason = "Round trip exceeds every drone's full usable capacity"
        if reason:
            if package.status != "EXPIRED":
                package.status = "REJECTED"
            package.outcome_reason = reason
            package.assigned_drone = -1
            package.decision_history.append({
                "sim_time": sim_time, "action": package.status,
                "reason": reason, "candidates": [],
            })





def summarize_packages(packages):
    counts = {status: 0 for status in (
        "PENDING", "ASSIGNED", "REJECTED", "EXPIRED", "DELIVERED_ON_TIME", "DELIVERED_LATE")}
    for package in packages.values():
        counts[package.status] += 1
    return counts


def save_run_report(packages, directory=DEFAULT_LOG_DIR, label="simulation", timing=None):
    """Unique run files preserve previous experiments and candidate explanations."""
    from datetime import datetime, timezone
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / (label + "-" + stamp + ".json")
    records = [{
        "package_id": p.id, "request_time": p.request_time, "deadline": p.deadline,
        "status": p.status, "assigned_drone": p.assigned_drone,
        "delivered_at": p.delivered_at, "reason": p.outcome_reason,
        "decisions": p.decision_history,
    } for p in packages.values()]
    report = {"summary": summarize_packages(packages), "packages": records}
    if timing is not None:
        report["timing"] = timing
    with path.open("x") as stream:
        json.dump(report, stream, indent=2)
    return path



def validate_fleet(drones, charging_pads, packages):
    validate_simulation(drones, charging_pads)

    for drone in drones.values():
        if drone.current_package is not None:
            package = packages[drone.current_package]
            assert package.assigned_drone == drone.id, f"Drone {drone.id} carries package {package.id} but package thinks it's assigned to {package.assigned_drone}"

    for package in packages.values():
        if package.assigned_drone not in (None, -1):
            assert package.assigned_drone in drones, f"Package {package.id} assigned to invalid drone {package.assigned_drone}"

def run_simulation_step(drone, packages, dt, sim_time, charging_pads, wind_events=None):
    if drone.status == "QUARANTINED":
        return
    update_drone(drone, packages, dt, charging_pads, sim_time, wind_events)

def initialize_drones(num_drones=10):
    drones = {}
    for i in range(1, num_drones + 1):
        drones[i] = DroneState(
            id=i,
            x=float(BASE[0]),
            y=float(BASE[1]),
            battery=100.0,
            battery_capacity=100.0,
            cycle_count=0,
            cycle_energy=0.0,
            status="IDLE",
            payload=0.0,
            target=None,
            total_distance=0.0,
            charging_pad=None,
            charge_remaining=0.0
        )
    return drones

DEFAULT_TIME_SCALE = 5.0  # 40 simulated minutes in about 8 real minutes.
SIMULATION_STEP = 0.25
DISPLAY_FRAME_INTERVAL = 1.0 / 30.0


def configure_gui_fonts():
    """Use installed fonts when the OpenCV wheel points Qt to missing fonts."""
    configured = os.environ.get("QT_QPA_FONTDIR")
    if configured and Path(configured).is_dir():
        return
    for directory in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation2",
                      "/usr/share/fonts/truetype/freefont"):
        if Path(directory).is_dir():
            os.environ["QT_QPA_FONTDIR"] = directory
            return


def run_demo(duration=40 * 60, time_scale=DEFAULT_TIME_SCALE, headless=False,
             algorithm="v2", log_dir=DEFAULT_LOG_DIR, seed=42,
             package_manifest=None, initial_batteries=None, workload_name="",
             decision_history_limit=None):
    wind_events = generate_wind_events(seed, duration)
    drones = initialize_drones()
    for drone_id, battery in (initial_batteries or {}).items():
        drones[drone_id].battery = battery
    requests = (None if package_manifest is None else
                iter(sorted(package_manifest.values(), key=lambda p: (p.request_time, p.id))))
    next_package = next(requests, None) if requests is not None else None
    packages = {}
    charging_pads = {1: None, 2: None, 3: None}
    env = None if headless else Drone2DEnvironment(num_drones=10)
    if env:
        configure_gui_fonts()
        cv2.namedWindow("Drone 2D Environment", cv2.WINDOW_NORMAL)
        env.update_state(drones, packages, list(charging_pads.values()),
                         message=f"{workload_name} {algorithm.upper()} | starting {time_scale:g}x playback")
        cv2.imshow("Drone 2D Environment", env.draw())
        cv2.waitKey(1)
    sim_time = 0.0
    next_request = 0.0
    wall_start = time.monotonic()
    try:
        while sim_time < duration:
            frame_start = time.monotonic()
            # Wall time only controls playback. All physical logic uses simulated seconds.
            target_time = duration if headless else min(duration, (frame_start - wall_start) * time_scale)
            while sim_time < target_time:
                dt = min(SIMULATION_STEP, duration - sim_time)
                while next_package is not None and next_package.request_time <= sim_time + 1e-9:
                    packages[next_package.id] = next_package
                    next_package = next(requests, None)
                if requests is None and sim_time + 1e-9 >= next_request:
                    package = generate_hard_package(len(packages) + 1, sim_time)
                    packages[package.id] = package
                    next_request += 10.0
                assignment.schedule_packages(drones, packages, sim_time, charging_pads, algorithm)
                for drone in drones.values():
                    run_simulation_step(drone, packages, dt, sim_time, charging_pads, wind_events)
                sim_time += dt
                update_package_outcomes(drones, packages, sim_time)
                validate_fleet(drones, charging_pads, packages)
                if decision_history_limit is not None:
                    for package in packages.values():
                        del package.decision_history[:-decision_history_limit]
                # Draw and handle input during catch-up rather than blocking for the entire backlog.
                if env and time.monotonic() - frame_start >= DISPLAY_FRAME_INTERVAL:
                    break
            if env:
                elapsed = time.monotonic() - wall_start
                routes = {d.id: [(d.x, d.y), d.target] for d in drones.values()
                          if d.target is not None}
                env.update_state(drones, packages, list(charging_pads.values()),
                                 routes=routes,
                                 playback_info={"real_seconds": elapsed,
                                                "actual_speed": sim_time / elapsed if elapsed > 0 else 0},
                                 message=f"{workload_name + ' ' if workload_name else ''}{algorithm.upper()} | {sim_time / 60:.1f} sim min | {time_scale:g}x playback")
                cv2.imshow("Drone 2D Environment", env.draw())
                delay_ms = max(1, round((DISPLAY_FRAME_INTERVAL - (time.monotonic() - frame_start)) * 1000))
                if cv2.waitKey(delay_ms) & 0xFF in (ord("q"), ord("Q"), 27):
                    break
    finally:
        elapsed = max(time.monotonic() - wall_start, 1e-9)
        timing = {"simulated_seconds": sim_time, "real_seconds": elapsed,
                  "actual_speed": sim_time / elapsed, "requested_speed": time_scale,
                  "headless": headless}
        path = save_run_report(packages, log_dir,
                               f"{algorithm}-{workload_name.lower()}" if workload_name else algorithm,
                               timing=timing)
        print(f"Timing: {sim_time:.2f} simulated seconds / {elapsed:.2f} real seconds "
              f"= {timing['actual_speed']:.2f}x actual speed"
              + (" (headless, unpaced)" if headless else f" (target: {time_scale:g}x)"))
        print("Outcomes:", summarize_packages(packages))
        print("Decision report:", path)
        if env:
            cv2.destroyAllWindows()
    return drones, packages


def main(argv=None, default_algorithm="v2"):
    parser = argparse.ArgumentParser(description="Accelerated drone fleet simulation")
    parser.add_argument("--minutes", type=float, default=40.0,
                        help="Simulated duration in minutes (default: 40)")
    parser.add_argument("--time-scale", type=float, default=DEFAULT_TIME_SCALE,
                        help="Playback speed multiplier (default: 5, so 40 simulated minutes take 8 real minutes)")
    parser.add_argument("--headless", action="store_true", help="Run without graphics or playback delays")
    parser.add_argument("--algorithm", choices=tuple(assignment.ALGORITHMS), default=default_algorithm,
                        help=f"Assignment algorithm (default: {default_algorithm})")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--seed", type=int, default=42, help="Random seed for wind events")
    args = parser.parse_args(argv)
    if not math.isfinite(args.minutes) or args.minutes <= 0 or not math.isfinite(args.time_scale) or args.time_scale <= 0:
        parser.error("minutes and time-scale must be finite positive numbers")
    run_demo(args.minutes * 60, args.time_scale, args.headless, args.algorithm, args.log_dir, args.seed)


if __name__ == "__main__":
    main()
