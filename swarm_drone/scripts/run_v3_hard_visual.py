"""Live V3 stress test with bursts, sustained arrivals, and low batteries."""

import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone.drone_sim import BASE, MAP_W, MAP_H, PackageState
from swarm_drone.paths import DEFAULT_LOG_DIR


def make_workload(duration, seed=42, initial_packages=30, arrival_interval=5.0,
                  burst_size=10, burst_interval=60.0):
    rng = random.Random(seed)
    manifest = {}

    def add_package(now):
        # Visible destinations retain the simulator's existing pixel/meter units.
        while True:
            x = rng.uniform(45, MAP_W - 90)
            y = rng.uniform(45, MAP_H - 45)
            if math.hypot(x - BASE[0], y - BASE[1]) >= 100:
                break
        package_id = len(manifest) + 1
        manifest[package_id] = PackageState(
            id=package_id, x=x, y=y, weight=rng.uniform(1.5, 2.5),
            request_time=now, deadline=now + rng.uniform(45, 120),
        )

    for _ in range(initial_packages):
        add_package(0.0)
    index = 1
    while index * arrival_interval < duration:
        add_package(index * arrival_interval)
        index += 1
    index = 1
    while index * burst_interval < duration:
        for _ in range(burst_size):
            add_package(index * burst_interval)
        index += 1
    # Matches the older HARD runner's 30 + 2*i percent starting batteries.
    batteries = {i: 30.0 + 2.0 * i for i in range(1, 11)}
    return manifest, batteries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=40.0)
    parser.add_argument("--time-scale", type=float, default=simulation.DEFAULT_TIME_SCALE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--initial-packages", type=int, default=30)
    parser.add_argument("--arrival-interval", type=float, default=5.0,
                        help="Simulated seconds between individual requests (default: 5)")
    parser.add_argument("--burst-size", type=int, default=10)
    parser.add_argument("--burst-interval", type=float, default=60.0,
                        help="Simulated seconds between bursts (default: 60)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    args = parser.parse_args(argv)
    timing = (args.minutes, args.time_scale, args.arrival_interval, args.burst_interval)
    if not all(math.isfinite(value) and value > 0 for value in timing):
        parser.error("duration, playback speed, and arrival/burst intervals must be finite and positive")
    if args.initial_packages < 0 or args.burst_size < 0:
        parser.error("package and burst counts must be nonnegative")
    manifest, batteries = make_workload(
        args.minutes * 60, args.seed, args.initial_packages,
        args.arrival_interval, args.burst_size, args.burst_interval,
    )
    print(f"V3 HARD: {len(manifest)} requests, 10 drones, 3 charging pads; "
          f"{args.minutes:g} simulated minutes at {args.time_scale:g}x speed.")
    print("Heavy payloads (1.5-2.5 kg), 45-120 second deadlines, 32-50% initial batteries.")
    print("Press Q or Esc to stop. Reports keep the last 5 decisions per package.")
    return simulation.run_demo(
        duration=args.minutes * 60, time_scale=args.time_scale,
        headless=args.headless, algorithm="v3", log_dir=args.log_dir, seed=args.seed,
        package_manifest=manifest, initial_batteries=batteries,
        workload_name="HARD", decision_history_limit=5,
    )


if __name__ == "__main__":
    main()
