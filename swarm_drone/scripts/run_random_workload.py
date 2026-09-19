import sys
import random
import contextlib
import io
import math
import argparse
import hashlib
import json
import statistics
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone.paths import DEFAULT_LOG_DIR
from swarm_drone import assignment
from swarm_drone import drone_sim
def generate_random_package(package_id, sim_time, rng=None):
    rng = rng or random
    # Random position FAR from base (donut shape 3000 to 6000 pixels away)
    angle = rng.uniform(0, 2 * math.pi)
    distance = rng.uniform(3000, 6000)
    dx = distance * math.cos(angle)
    dy = distance * math.sin(angle)
    x = drone_sim.BASE[0] + dx
    y = drone_sim.BASE[1] + dy
    
    # Heavy payload between 1.5 and 2.5 kg (max capacity)
    weight = rng.uniform(1.5, 2.5)
    
    # Distance to package
    dist_pixels = math.sqrt(dx**2 + dy**2)
    dist_meters = simulation.pixels_to_meters(dist_pixels)
    
    # Very strict deadline based on flight time + minimal slack
    flight_time = (dist_meters * 2) / simulation.calculate_speed(weight)
    slack = rng.uniform(20.0, 100.0) # Adjusted for longer flights
    deadline = sim_time + flight_time + slack
    
    return drone_sim.PackageState(
        id=package_id,
        x=float(x),
        y=float(y),
        weight=weight,
        request_time=sim_time,
        deadline=deadline,
        assigned_drone=None,
        delivered=False
    )

FIXED_SEEDS = (42, 100, 2026)
DURATION_SECONDS = 100 * 60
TIMESTEP = 1.0


class WaitTracker:
    """Grid-sampled low-battery wait at base; no scheduler status categories."""
    def __init__(self, drones):
        self.starts = {d:None for d in drones}
        self.episodes = {d:[] for d in drones}

    def observe(self, drones, pads, now):
        for drone_id, drone in drones.items():
            blocked = (drone.status == "WAITING_FOR_CHARGE")
            start = self.starts[drone_id]
            if blocked and start is None:
                self.starts[drone_id] = now
            elif not blocked and start is not None:
                self.episodes[drone_id].append(
                    dict(start=start, end=now, duration=now-start, ongoing=False))
                self.starts[drone_id] = None

    def finish(self, now):
        for drone_id, start in self.starts.items():
            if start is not None:
                self.episodes[drone_id].append(
                    dict(start=start, end=now, duration=now-start, ongoing=True))
                self.starts[drone_id] = None
        return {
            drone_id: dict(total_wait=sum(e["duration"] for e in episodes),
                           max_single_wait=max((e["duration"] for e in episodes), default=0.0),
                           episodes=episodes)
            for drone_id, episodes in self.episodes.items()
        }


def make_workload(seed):
    # Replay the same RNG draw order as the original workload, once per seed.
    rng = random.Random(seed)
    batteries = {i:rng.uniform(15.0, 40.0) for i in range(1,11)}
    requests = []
    for _ in range(rng.randint(5,10)):
        requests.append(generate_random_package(len(requests)+1, 0.0, rng))
    for now in range(DURATION_SECONDS):
        if rng.random() < TIMESTEP/rng.uniform(5.0,15.0):
            requests.append(generate_random_package(len(requests)+1, float(now), rng))
    manifest = dict(seed=seed, batteries=batteries, requests=[asdict(p) for p in requests],
                    duration=DURATION_SECONDS, timestep=TIMESTEP)
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return dict(batteries=batteries, requests=requests, fingerprint=fingerprint, seed=seed)


def run_random_experiment(scheduler_func, name, num_pads=3, seed=42,
                          workload=None, log_dir=DEFAULT_LOG_DIR, save_decisions=True, verbose=True):
    workload = make_workload(seed) if workload is None else workload
    if workload["seed"] != seed:
        raise ValueError("Workload seed does not match requested seed")
    drones = simulation.initialize_drones(10)
    for drone_id, drone in drones.items():
        drone.battery = workload["batteries"][drone_id]
    packages, pads = {}, {i:None for i in range(1,num_pads+1)}
    tracker = WaitTracker(drones)
    index = 0
    pad_time = {pad:0.0 for pad in pads}
    recovery_ticks = 0
    failures = set()
    for tick in range(DURATION_SECONDS):
        now = float(tick)
        while index < len(workload["requests"]) and workload["requests"][index].request_time <= now:
            original = workload["requests"][index]
            packages[original.id] = replace(original, decision_history=[])
            index += 1
        # Observe both sides of instantaneous scheduler changes at the same time.
        tracker.observe(drones, pads, now)
        scheduler_func(drones, packages, now, pads)
        tracker.observe(drones, pads, now)
        for pad, occupant in pads.items():
            if occupant is not None:
                pad_time[pad] += TIMESTEP
        recovery_ticks += sum(d.recovery_charging for d in drones.values())*TIMESTEP
        for drone in drones.values():
            simulation.run_simulation_step(drone, packages, TIMESTEP, now, pads)
            if drone.status == "FAILED":
                failures.add(drone.id)
        simulation.validate_fleet(drones, pads, packages)
        tracker.observe(drones, pads, now+TIMESTEP)
        # Validation runs can omit bulky candidate logs without changing decisions.
        if not save_decisions:
            for p in packages.values():
                p.decision_history.clear()
    simulation.update_package_outcomes(drones, packages, DURATION_SECONDS)
    outcomes = simulation.summarize_packages(packages)
    assert sum(outcomes.values()) == len(packages) == len(workload["requests"])
    waits = tracker.finish(float(DURATION_SECONDS))
    metrics = dict(
        policy=name, seed=seed, workload_fingerprint=workload["fingerprint"],
        packages_generated=len(packages), outcomes=outcomes,
        packages_delivered=outcomes["DELIVERED_ON_TIME"]+outcomes["DELIVERED_LATE"],
        packages_on_time=outcomes["DELIVERED_ON_TIME"], packages_late=outcomes["DELIVERED_LATE"],
        packages_rejected=outcomes["REJECTED"], packages_expired=outcomes["EXPIRED"],
        packages_pending=outcomes["PENDING"], packages_in_flight=outcomes["ASSIGNED"],
        mean_total_wait=statistics.mean(w["total_wait"] for w in waits.values()),
        max_single_wait=max(w["max_single_wait"] for w in waits.values()),
        waits_by_drone=waits, failed_drones=sorted(failures),
        pad_utilization=100*sum(pad_time.values())/(max(num_pads,1)*DURATION_SECONDS),
        total_energy_used=sum(d.cycle_count*100+d.cycle_energy for d in drones.values()),
        total_flight_seconds=sum(d.total_flight_time for d in drones.values()),
        end_stored_energy=sum(d.battery for d in drones.values()),
        recovery_drone_seconds=recovery_ticks,
        reserve_fraction=0.20,
        low_battery_fraction=0.10,
        fairness_threshold_seconds=0.0)
    if save_decisions:
        metrics["decision_report"] = str(simulation.save_run_report(
            packages, log_dir, label=f"{scheduler_func.__name__}-seed{seed}"))
    if verbose:
        print(f"Seed {seed} | {name} | {outcomes}", flush=True)
        print(f"  Mean total wait: {metrics['mean_total_wait']:.1f}s | "
              f"Longest observed episode: {metrics['max_single_wait']:.1f}s | "
              f"Pads: {metrics['pad_utilization']:.1f}% | Failed: {len(failures)}", flush=True)
    return metrics


def aggregate_results(results):
    summary = {}
    for policy in sorted({r["policy"] for r in results}):
        runs = [r for r in results if r["policy"] == policy]
        stats = {}
        for metric in ("packages_on_time","packages_late","packages_rejected","packages_expired",
                       "packages_pending","packages_in_flight","mean_total_wait","max_single_wait",
                       "pad_utilization","total_energy_used"):
            values = [r[metric] for r in runs]
            stats[metric] = dict(mean=statistics.mean(values),
                                sample_std=statistics.stdev(values) if len(values)>1 else 0.0)
        stats["worst_observed_episode"] = max(r["max_single_wait"] for r in runs)
        stats["failed_drones"] = sum(len(r["failed_drones"]) for r in runs)
        summary[policy] = stats
    return summary


def run_benchmarks(seeds=FIXED_SEEDS, log_dir=DEFAULT_LOG_DIR, save_decisions=True,
                   policy_names=("baseline", "v1", "v2")):
    def baseline_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "baseline")
    def v1_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "v1")
    def v2_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "v2")
    available_policies = {
        "baseline": ("Baseline", baseline_scheduler),
        "v1": ("V1", v1_scheduler),
        "v2": ("V2", v2_scheduler),
    }
    if not policy_names or len(set(policy_names)) != len(policy_names) or any(
            name not in available_policies for name in policy_names):
        raise ValueError("Choose distinct policies from baseline, v1, v2")
    policies = tuple(available_policies[name] for name in policy_names)
    results = []
    for seed in seeds:
        workload = make_workload(seed)
        paired = []
        for name, scheduler in policies:
            result = run_random_experiment(scheduler, name, seed=seed, workload=workload,
                                           log_dir=log_dir, save_decisions=save_decisions)
            results.append(result)
            paired.append(result)
        assert len({r["workload_fingerprint"] for r in paired}) == 1
    summary = aggregate_results(results)
    deltas = [next(r["packages_on_time"] for r in results if r["seed"]==seed and r["policy"]=="V2")
              - next(r["packages_on_time"] for r in results if r["seed"]==seed and r["policy"]=="V1")
              for seed in seeds] if {"v1", "v2"}.issubset(policy_names) else []
    for policy, stats in summary.items():
        on_time = stats["packages_on_time"]
        print(f"{policy}: on-time {on_time['mean']:.2f} +/- {on_time['sample_std']:.2f}; "
              f"worst observed wait {stats['worst_observed_episode']:.1f}s", flush=True)
    if deltas:
        print("Paired V2 minus V1 on-time differences:", dict(zip(seeds,deltas)), flush=True)
    report = dict(seeds=list(seeds), runs=results, summary=summary,
                  paired_on_time_deltas=deltas,
                  notes=["Means and sample standard deviations; three seeds do not prove significance.",
                         "Wait is low battery at base without a pad, not proof of inability to deliver.",
                         "Episode boundaries and pad utilization sampled on the 1-second grid.",
                         "Ongoing episodes are censored observations at experiment end."])
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("benchmark-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    with path.open("x") as stream:
        json.dump(report, stream, indent=2)
    print("Benchmark report:", path, flush=True)
    return report, path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paired fixed-seed fleet evaluation")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(FIXED_SEEDS))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--no-decision-logs", action="store_true")
    parser.add_argument("--policies", nargs="+", choices=("baseline", "v1", "v2", "fsm"),
                        default=["baseline", "v1", "v2"], help="Policies to run; FSM is opt-in")
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("Seeds must be distinct")
    if len(set(args.policies)) != len(args.policies):
        parser.error("Policies must be distinct")
    run_benchmarks(args.seeds, args.log_dir, not args.no_decision_logs, args.policies)
