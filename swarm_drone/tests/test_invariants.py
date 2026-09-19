import unittest
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone import assignment
from swarm_drone.wind import generate_wind_events
from scripts.run_extreme_workload import generate_extreme_workload

class TestInvariants(unittest.TestCase):
    def test_extreme_workload_invariants(self):
        duration = 10 * 60.0
        seed = 99
        
        packages_manifest = generate_extreme_workload(seed=seed, duration=duration)
        wind_events = generate_wind_events(seed=seed, max_time=duration)
        
        drones = simulation.initialize_drones(10)
        pads = {1: None, 2: None, 3: None}
        
        sim_time = 0.0
        dt_sim = 1.0
        active_packages = {}
        
        while sim_time < duration:
            for p_id, p in packages_manifest.items():
                if p_id not in active_packages and p.request_time <= sim_time:
                    active_packages[p.id] = p
            
            simulation.quarantine_invalid_drones(drones, active_packages, pads, sim_time)
            
            assignment.schedule_packages(drones, active_packages, sim_time, pads, "v2")
            
            for d in drones.values():
                if d.status == "QUARANTINED":
                    self.assertIsNone(d.current_package, "Quarantined drone must not have an active package")
            
            for drone in drones.values():
                simulation.run_simulation_step(drone, active_packages, dt_sim, sim_time, pads, wind_events)
            
            simulation.validate_fleet(drones, pads, active_packages)
            
            assigned_pkgs = set()
            for drone in drones.values():
                if drone.status != "QUARANTINED":
                    self.assertGreaterEqual(drone.battery, -1e-6)
                    self.assertLessEqual(drone.battery, drone.battery_capacity + 1e-6)
                
                self.assertLessEqual(drone.payload, 2.5 + 1e-6)
                
                if drone.current_package is not None:
                    self.assertNotIn(drone.current_package, assigned_pkgs, "Package assigned to multiple drones!")
                    assigned_pkgs.add(drone.current_package)
                    
            for pkg in active_packages.values():
                if pkg.assigned_drone is not None and pkg.assigned_drone != -1:
                    if pkg.status == "ASSIGNED":
                        d = drones[pkg.assigned_drone]
                        if d.status != "QUARANTINED":
                            self.assertEqual(d.current_package, pkg.id, "Package assigned_drone mismatch")

            pad_owners = set()
            for pad_id, drone_id in pads.items():
                if drone_id is not None:
                    self.assertNotIn(drone_id, pad_owners, "Drone occupying multiple pads!")
                    pad_owners.add(drone_id)
            
            sim_time += dt_sim

if __name__ == '__main__':
    unittest.main()
