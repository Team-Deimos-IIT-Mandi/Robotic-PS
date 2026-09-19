import sys
from pathlib import Path
import random
import math
import contextlib
import io
import argparse
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone import drone_sim
from swarm_drone import assignment
from swarm_drone.paths import DEFAULT_BENCHMARK_DIR
from swarm_drone.wind import generate_wind_events

def generate_extreme_workload(seed=999, duration=60*60):
    rng = random.Random(seed)
    packages = []
    
    sim_time = 0.0
    package_id = 1
    
    # Inject 10 highly feasible packages at t=1.0 to swamp the fleet immediately
    for _ in range(10):
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(500, 1000) # Close by
        x = drone_sim.BASE[0] + distance * math.cos(angle)
        y = drone_sim.BASE[1] + distance * math.sin(angle)
        
        dist_m = distance / 10.0
        min_flight_time = (dist_m * 2) / 15.0
        deadline = 1.0 + min_flight_time + 600.0 # Very generous deadline
        
        packages.append(drone_sim.PackageState(
            id=package_id, x=float(x), y=float(y), weight=1.0,
            request_time=1.0, deadline=deadline,
            assigned_drone=None, delivered=False
        ))
        package_id += 1
        
    sim_time = 10.0
    
    while sim_time < duration:
        event = rng.choices(["burst", "drought", "trickle"], weights=[20, 20, 60])[0]
        if event == "burst":
            num_pkgs = rng.randint(10, 15)
            for _ in range(num_pkgs):
                packages.append(create_chaotic_package(package_id, sim_time, rng))
                package_id += 1
            sim_time += rng.uniform(10.0, 60.0) 
        elif event == "drought":
            sim_time += rng.uniform(300.0, 900.0)
        elif event == "trickle":
            num_pkgs = rng.randint(1, 5)
            for _ in range(num_pkgs):
                sim_time += rng.uniform(10.0, 120.0)
                if sim_time < duration:
                    packages.append(create_chaotic_package(package_id, sim_time, rng))
                    package_id += 1
    return {p.id: p for p in packages}

def create_chaotic_package(pkg_id, sim_time, rng):
    angle = rng.uniform(0, 2 * math.pi)
    distance = rng.uniform(500, 8000)
    x = drone_sim.BASE[0] + distance * math.cos(angle)
    y = drone_sim.BASE[1] + distance * math.sin(angle)
    
    weight_type = rng.choices(["light", "heavy", "overweight"], weights=[50, 40, 10])[0]
    if weight_type == "light": weight = rng.uniform(0.1, 1.0)
    elif weight_type == "heavy": weight = rng.uniform(1.5, 2.5)
    else: weight = rng.uniform(2.51, 3.5)
        
    dist_m = distance / 10.0
    min_flight_time = (dist_m * 2) / 15.0
    
    deadline_type = rng.choices(["impossible", "tight", "generous"], weights=[10, 60, 30])[0]
    if deadline_type == "impossible": deadline = sim_time + min_flight_time * rng.uniform(0.1, 0.9)
    elif deadline_type == "tight": deadline = sim_time + min_flight_time + rng.uniform(10.0, 60.0)
    else: deadline = sim_time + min_flight_time + rng.uniform(300.0, 600.0)
        
    return drone_sim.PackageState(
        id=pkg_id, x=float(x), y=float(y), weight=weight,
        request_time=sim_time, deadline=deadline,
        assigned_drone=None, delivered=False
    )

def run_single_algorithm(algorithm, packages_manifest, wind_events, duration,
                         scheduler_options=None):
    drones = simulation.initialize_drones(10)
    rng = random.Random(123)
    for d in drones.values(): d.battery = rng.uniform(10.0, 100.0)
    pads = {1: None, 2: None, 3: None}
    
    sim_time = 0.0
    dt_sim = 1.0
    active_packages = {}
    
    total_energy = 0.0
    peak_charging_queue = 0
    peak_airborne = 0
    initial_energy = {d.id: d.battery for d in drones.values()}
    
    with contextlib.redirect_stdout(io.StringIO()):
        while sim_time < duration:
            for p_id, p in packages_manifest.items():
                if p_id not in active_packages and p.request_time <= sim_time:
                    active_packages[p.id] = p
            
            simulation.quarantine_invalid_drones(drones, active_packages, pads, sim_time)
            assignment.schedule_packages(drones, active_packages, sim_time, pads, algorithm,
                                         **(scheduler_options or {}))
            peak_charging_queue = max(peak_charging_queue, sum(
                d.status == "WAITING_FOR_CHARGE" for d in drones.values()))
            peak_airborne = max(peak_airborne, sum(
                d.status in ("DELIVERY", "RETURNING") for d in drones.values()))
            
            for drone in drones.values():
                old_batt = drone.battery
                simulation.run_simulation_step(drone, active_packages, dt_sim, sim_time, pads, wind_events)
                if drone.battery < old_batt:
                    total_energy += (old_batt - drone.battery)
                
            simulation.validate_fleet(drones, pads, active_packages)
            peak_charging_queue = max(peak_charging_queue, sum(
                d.status == "WAITING_FOR_CHARGE" for d in drones.values()))
            sim_time += dt_sim
            
    for package in active_packages.values():
        if package.status == "PENDING" and package.deadline < sim_time:
            package.status = "EXPIRED"
            package.outcome_reason = "Deadline passed while waiting"
            
    outcomes = simulation.summarize_packages(active_packages)
    total_distance = sum(d.total_distance for d in drones.values())
    
    return {
        "outcomes": outcomes,
        "energy": total_energy,
        "distance": total_distance,
        "packages": active_packages,
        "peak_charging_queue": peak_charging_queue,
        "peak_airborne": peak_airborne,
        "charge_wait_seconds": sum(d.total_charge_wait_time for d in drones.values()),
        "failed_drones": sum(d.status == "FAILED" for d in drones.values()),
    }

def print_package_trace(package):
    print(f"\nTrace for Package {package.id} (Status: {package.status})")
    print(f"Arrival: {package.request_time:.1f}s | Deadline: {package.deadline:.1f}s")
    for dec in package.decision_history:
        act = dec["action"]
        t = dec["sim_time"]
        if act == "DEFERRED":
            cands = dec.get("candidates", [])
            feasible = sum(1 for c in cands if not c["reasons"])
            print(f"  t={t:6.1f}s | {act:10s} | Feasible drones: {feasible}/{len(cands)}")
            if feasible > 0:
                print(f"             | Reason: {dec.get('reason')}")
        else:
            print(f"  t={t:6.1f}s | {act:10s} | {dec.get('reason', '')}")
            
def generate_hard_workload(duration):
    return {
        i + 1: simulation.generate_hard_package(i + 1, float(i * 10))
        for i in range(math.ceil(duration / 10.0))
    }


def run_comparison(duration=60 * 60.0, seed=42, workload="extreme",
                   min_reserve=None, traces=True):
    
    print(f"Generating deterministic {workload} workload (seed={seed}, duration={duration:g}s)...", flush=True)
    def manifest():
        return (generate_hard_workload(duration) if workload == "hard"
                else generate_extreme_workload(seed=seed, duration=duration))
    pkgs_base = manifest()
    pkgs_v1 = manifest()
    pkgs_v2 = manifest()
    pkgs_v3 = manifest()
    wind_events = generate_wind_events(seed=seed, max_time=duration)
    
    print("Running Baseline (Greedy)...", flush=True)
    res_base = run_single_algorithm("baseline", pkgs_base, wind_events, duration)
    
    print("Running Global (V1)...", flush=True)
    res_v1 = run_single_algorithm("v1", pkgs_v1, wind_events, duration)
    
    print("Running Global Max-Coverage (V2)...", flush=True)
    res_v2 = run_single_algorithm("v2", pkgs_v2, wind_events, duration)
    
    print("Running Predictive Max-Coverage (V3)...", flush=True)
    res_v3 = run_single_algorithm("v3", pkgs_v3, wind_events, duration,
                                  {"min_reserve": min_reserve})
    
    b_out = res_base["outcomes"]
    v1_out = res_v1["outcomes"]
    v_out = res_v2["outcomes"]
    v3_out = res_v3["outcomes"]
    
    total_requests = len(pkgs_base)
    physically_impossible = 0
    ideal = drone_sim.DroneState(id=0, x=float(drone_sim.BASE[0]), y=float(drone_sim.BASE[1]))
    from swarm_drone.physics import calculate_delivery_time
    for p in pkgs_base.values():
        if p.weight > 2.5 or (p.request_time + calculate_delivery_time(ideal, p) > p.deadline):
            physically_impossible += 1
            
    feasible_requests = total_requests - physically_impossible
    
    b_ontime = b_out['DELIVERED_ON_TIME']
    v1_ontime = v1_out['DELIVERED_ON_TIME']
    v_ontime = v_out['DELIVERED_ON_TIME']
    v3_ontime = v3_out['DELIVERED_ON_TIME']
    
    b_pct = (b_ontime / feasible_requests) * 100.0 if feasible_requests else 0.0
    v1_pct = (v1_ontime / feasible_requests) * 100.0 if feasible_requests else 0.0
    v_pct = (v_ontime / feasible_requests) * 100.0 if feasible_requests else 0.0
    v3_pct = (v3_ontime / feasible_requests) * 100.0 if feasible_requests else 0.0
    
    print("\n========================================================")
    print("           ALGORITHM COMPARISON REPORT")
    print("========================================================")
    print(f"Total requests:              {total_requests}")
    print(f"Physically impossible:        {physically_impossible}")
    print(f"Feasible requests:           {feasible_requests}\n")
    
    print("| Metric             | Greedy             | Global (V1)        | Global (V2)        | Predictive (V3)    |")
    print("| ------------------ | ------------------ | ------------------ | ------------------ | ------------------ |")
    print(f"| On-time deliveries | {b_ontime:2d}/{feasible_requests} ({b_pct:4.1f}%) | {v1_ontime:2d}/{feasible_requests} ({v1_pct:4.1f}%) | {v_ontime:2d}/{feasible_requests} ({v_pct:4.1f}%) | {v3_ontime:2d}/{feasible_requests} ({v3_pct:4.1f}%) |")
    print(f"| Expired            | {b_out['EXPIRED']:6d}             | {v1_out['EXPIRED']:6d}             | {v_out['EXPIRED']:6d}             | {v3_out['EXPIRED']:6d}             |")
    print(f"| Rejected           | {b_out['REJECTED']:6d}             | {v1_out['REJECTED']:6d}             | {v_out['REJECTED']:6d}             | {v3_out['REJECTED']:6d}             |")
    print(f"| Total energy       | {res_base['energy']:6.1f}             | {res_v1['energy']:6.1f}             | {res_v2['energy']:6.1f}             | {res_v3['energy']:6.1f}             |")
    print(f"| Total distance     | {res_base['distance']:6.1f}             | {res_v1['distance']:6.1f}             | {res_v2['distance']:6.1f}             | {res_v3['distance']:6.1f}             |")
    for label, key in (("Peak charge queue", "peak_charging_queue"),
                       ("Peak airborne", "peak_airborne"),
                       ("Charge wait (s)", "charge_wait_seconds"),
                       ("Failed drones", "failed_drones")):
        values = " | ".join(f"{result[key]:18.1f}" for result in (res_base, res_v1, res_v2, res_v3))
        print(f"| {label:18s} | {values} |")
    for status in ("PENDING", "ASSIGNED", "DELIVERED_LATE"):
        values = " | ".join(f"{result['outcomes'][status]:18d}" for result in (res_base, res_v1, res_v2, res_v3))
        print(f"| {status:18s} | {values} |")
    
    if traces:
        print("\n--- Detailed Traces for Selected Packages (Predictive V3 Run) ---")
        v3_pkgs = res_v3["packages"]
        for pid in [19, 33, 49]:
            if pid in v3_pkgs:
                print_package_trace(v3_pkgs[pid])
    return {"baseline": res_base, "v1": res_v1, "v2": res_v2, "v3": res_v3}

def save_comparison_report(results, duration, seed, workload, min_reserve,
                           directory=DEFAULT_BENCHMARK_DIR):
    import json
    from datetime import datetime, timezone
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{workload}-seed{seed}-{stamp}.json"
    report = {
        "workload": workload, "seed": seed, "duration_seconds": duration,
        "min_reserve": min_reserve,
        "algorithms": {
            name: {key: value for key, value in result.items() if key != "packages"}
            for name, result in results.items()
        },
    }
    with path.open("x") as stream:
        json.dump(report, stream, indent=2)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare schedulers on extreme or HARD workloads")
    parser.add_argument("--workload", choices=("extreme", "hard"), default="extreme")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--min-reserve", type=int, default=assignment.MIN_RESERVE)
    parser.add_argument("--no-traces", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_BENCHMARK_DIR))
    args = parser.parse_args()
    if not math.isfinite(args.minutes) or args.minutes <= 0 or args.min_reserve < 0:
        parser.error("minutes must be finite and positive; min-reserve must be nonnegative")
    results = run_comparison(args.minutes * 60.0, args.seed, args.workload, args.min_reserve, not args.no_traces)
    path = save_comparison_report(results, args.minutes * 60.0, args.seed,
                                   args.workload, args.min_reserve, args.output_dir)
    print("Comparison report:", path)
