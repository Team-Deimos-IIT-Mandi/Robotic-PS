import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone import assignment
from swarm_drone import drone_sim
import contextlib, io

def run_experiment(scheduler_func, name, num_pads=3):
    drones = simulation.initialize_drones(10)
    # Start drones at 30-50% battery to force them into charging quickly
    for i, drone in drones.items():
        drone.battery = 30.0 + (i * 2.0)
    packages = {}
    charging_pads = {i: None for i in range(1, num_pads + 1)}
    
    sim_time = 0.0
    dt_sim = 1.0
    total_time = 10 * 60.0 # 10 minutes
    next_package_id = 1
    
    metrics = {
        "packages_generated": 0,
        "packages_delivered": 0,
        "packages_expired": 0,
        "packages_pending": 0,
        "drone_active_time": {i: 0.0 for i in range(1, 11)},
        "drone_charging_time": {i: 0.0 for i in range(1, 11)},
        "drone_energy_consumed": {i: 0.0 for i in range(1, 11)},
        "pad_active_time": {i: 0.0 for i in range(1, num_pads + 1)}
    }
    
    for i in range(5):
        pkg = simulation.generate_hard_package(next_package_id, sim_time)
        packages[pkg.id] = pkg
        next_package_id += 1
        metrics["packages_generated"] += 1
    
    last_battery = {i: drones[i].battery for i in range(1, 11)}
    
    with contextlib.redirect_stdout(io.StringIO()): # Suppress noisy per-package logs
        while sim_time < total_time:
            if simulation.should_create_hard_package(sim_time):
                pkg = simulation.generate_hard_package(next_package_id, sim_time)
                packages[pkg.id] = pkg
                next_package_id += 1
                metrics["packages_generated"] += 1
                
            scheduler_func(drones, packages, sim_time, charging_pads)
            
            for drone in drones.values():
                simulation.run_simulation_step(drone, packages, dt_sim, sim_time, charging_pads)
                
                if drone.status != "IDLE":
                    metrics["drone_active_time"][drone.id] += dt_sim
                if drone.status == "CHARGING":
                    metrics["drone_charging_time"][drone.id] += dt_sim
                    
                if drone.battery < last_battery[drone.id]:
                    metrics["drone_energy_consumed"][drone.id] += (last_battery[drone.id] - drone.battery)
                last_battery[drone.id] = drone.battery
                
            for pad_id, occupant in charging_pads.items():
                if occupant is not None:
                    metrics["pad_active_time"][pad_id] += dt_sim
                    
            simulation.validate_fleet(drones, charging_pads, packages)
            sim_time += dt_sim
            
    simulation.update_package_outcomes(drones, packages, sim_time)
    outcomes = simulation.summarize_packages(packages)
    metrics["packages_delivered"] = outcomes["DELIVERED_ON_TIME"] + outcomes["DELIVERED_LATE"]
    metrics["packages_on_time"] = outcomes["DELIVERED_ON_TIME"]
    metrics["packages_late"] = outcomes["DELIVERED_LATE"]
    metrics["packages_rejected"] = outcomes["REJECTED"]
    metrics["packages_expired"] = outcomes["EXPIRED"]
    metrics["packages_pending"] = outcomes["PENDING"]
    metrics["packages_in_flight"] = outcomes["ASSIGNED"]
    report = simulation.save_run_report(packages, label=scheduler_func.__name__)
    print("Outcomes:", outcomes)
    print("Decision report:", report)
            
    print(f"\n--- {name} RESULTS (10 MIN) ---")
    print(f"Packages Generated: {metrics['packages_generated']}")
    print(f"Packages Delivered: {metrics['packages_delivered']}")
    print(f"Packages Expired:   {metrics['packages_expired']}")
    print(f"Packages Pending:   {metrics['packages_pending']}\n")
    
    print("Drone Metrics (Utilization = active / total_time):")
    utils = []
    waits = []
    for i in range(1, 11):
        utilization = (metrics["drone_active_time"][i] / total_time) * 100
        utils.append(utilization)
        distance = drones[i].total_distance
        energy = metrics["drone_energy_consumed"][i]
        charge = metrics["drone_charging_time"][i]
        wait = drones[i].total_charge_wait_time
        waits.append(wait)
        print(f"  D{i}: Util={utilization:5.1f}% | Dist={distance:6.1f}px | Energy={energy:6.1f} | Charge={charge:5.1f}s | Wait={wait:5.1f}s")
        
    avg_util = sum(utils) / len(utils)
    var_util = sum((u - avg_util)**2 for u in utils) / len(utils)
    print(f"\n  Avg Utilization: {avg_util:5.1f}%")
    print(f"  Utilization Variance: {var_util:5.1f}")
    
    avg_wait = sum(waits) / len(waits)
    max_wait = max(waits)
    print(f"  Avg Charging Wait: {avg_wait:5.1f}s")
    print(f"  Max Charging Wait: {max_wait:5.1f}s")
        
    print("\nPad Utilization:")
    for i in range(1, num_pads + 1):
        pad_util = (metrics["pad_active_time"][i] / total_time) * 100
        print(f"  Pad {i}: {pad_util:5.1f}%")
        
    return metrics

if __name__ == "__main__":
    def baseline_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "baseline")
    def v1_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "v1")
    def v2_scheduler(d, p, t, c): assignment.schedule_packages(d, p, t, c, "v2")

    run_experiment(baseline_scheduler, "BASELINE A", num_pads=3)
    run_experiment(v1_scheduler, "V1 (Weighted Cost)", num_pads=3)
    run_experiment(v2_scheduler, "V2.1 (Opportunistic Partial)", num_pads=3)
