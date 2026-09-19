import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import copy
import random
from scripts.run_extreme_workload import generate_extreme_workload, run_single_algorithm
from swarm_drone.wind import generate_wind_events
from swarm_drone.drone_sim import BASE

def main():
    pkgs = generate_extreme_workload(seed=42, duration=3600)
    wind = generate_wind_events(seed=42, max_time=3600)

    res = run_single_algorithm("v3", pkgs, wind, 3600)
    packages = res["packages"]

    print("--- SHOCK PACKAGES (ID 1-10) DELIVERIES ---")
    for i in range(1, 11):
        p = packages[i]
        print(f"\nPackage {i}:")
        for entry in p.decision_history:
            print(f"  t={entry['sim_time']} | {entry['action']}")
        print(f"  Final Status: {p.status}")


if __name__ == "__main__":
    main()
