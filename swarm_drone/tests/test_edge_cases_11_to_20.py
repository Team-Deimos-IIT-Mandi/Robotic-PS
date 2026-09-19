import unittest
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone.drone_sim import DroneState, PackageState, BASE
from swarm_drone import assignment
from swarm_drone import fsm
from swarm_drone import simulation
from swarm_drone import drone_sim
from swarm_drone import charging
from swarm_drone import physics
class TestEdgeCases11To20(unittest.TestCase):
    def setUp(self):
        pass

    def _create_package(self, id, weight, deadline, dx, dy):
        return PackageState(
            id=id,
            x=float(BASE[0] + dx),
            y=float(BASE[1] + dy),
            weight=weight,
            request_time=0.0,
            deadline=deadline,
            assigned_drone=None,
            delivered=False
        )

    def _create_drone(self, id, status="IDLE", battery=100.0, charging_pad=None):
        return DroneState(
            id=id,
            x=float(BASE[0]),
            y=float(BASE[1]),
            battery=battery,
            battery_capacity=100.0,
            cycle_count=0,
            cycle_energy=0.0,
            status=status,
            payload=0.0,
            target=None,
            total_distance=0.0,
            charging_pad=charging_pad,
            charge_remaining=0.0
        )

    def test_11_wind_makes_delivery_late(self):
        packages = {1: self._create_package(1, 1.0, 50.0, 4500, 0)}
        drones = {1: self._create_drone(1, status="DELIVERY")}
        drones[1].x = BASE[0] + 2000.0
        drones[1].current_package = 1
        drones[1].target = (packages[1].x, packages[1].y)
        packages[1].assigned_drone = 1
        
        wind_events = [{
            'start': 0.0, 'end': 100.0,
            'x': drones[1].x, 'y': drones[1].y, 'r': 10000.0,
            'vx': -15.0, 'vy': 0.0
        }]
        pads = {1: None}
        simulation.update_drone(drones[1], packages, 1.0, pads, sim_time=0.0, wind_events=wind_events)
        
        self.assertEqual(drones[1].status, "RETURNING")
        self.assertTrue(hasattr(packages[1], 'decision_history'))
        self.assertEqual(packages[1].decision_history[-1]["action"], "ABORTED")

    def test_12_delivery_possible_return_unsafe(self):
        packages = {1: self._create_package(1, 1.0, 500.0, 4500, 0)}
        drones = {1: self._create_drone(1, status="DELIVERY")}
        drones[1].x = BASE[0] + 2000.0
        
        ideal_energy = physics.calculate_required_battery(drones[1], packages[1])
        drones[1].battery = ideal_energy * 1.15
        drones[1].current_package = 1
        drones[1].target = (packages[1].x, packages[1].y)
        packages[1].assigned_drone = 1
        
        wind_events = [{
            'start': 0.0, 'end': 100.0,
            'x': drones[1].x, 'y': drones[1].y, 'r': 10000.0,
            'vx': 15.0, 'vy': 0.0
        }]
        pads = {1: None}
        simulation.update_drone(drones[1], packages, 1.0, pads, sim_time=0.0, wind_events=wind_events)
        
        self.assertEqual(drones[1].status, "RETURNING")
        self.assertEqual(packages[1].decision_history[-1]["action"], "ABORTED")

    def test_13_aborted_package_ownership(self):
        packages = {1: self._create_package(1, 1.0, 500.0, 4500, 0)}
        drones = {1: self._create_drone(1, status="DELIVERY")}
        
        drones[1].current_package = 1
        drones[1].payload = packages[1].weight
        packages[1].assigned_drone = 1
        packages[1].status = "ASSIGNED"
        
        fsm.abort_mission(drones[1], packages[1], 0.0, "Test Abort")
        
        self.assertEqual(drones[1].status, "RETURNING")
        self.assertEqual(drones[1].current_package, 1)
        self.assertEqual(drones[1].payload, 1.0)
        self.assertEqual(packages[1].assigned_drone, 1)
        
        fsm.return_to_base(drones[1], packages, 10.0)
        
        self.assertIsNone(drones[1].current_package)
        self.assertEqual(drones[1].payload, 0.0)
        self.assertIsNone(packages[1].assigned_drone)
        self.assertEqual(packages[1].status, "PENDING")

    def test_14_package_not_assigned_to_two_drones(self):
        packages = {1: self._create_package(1, 1.0, 500.0, 4500, 0)}
        drones = {
            1: self._create_drone(1, status="IDLE"),
            2: self._create_drone(2, status="IDLE")
        }
        pads = {1: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        simulation.validate_fleet(drones, pads, packages)
        
        assigned_drones = [d for d in drones.values() if d.current_package == 1]
        self.assertEqual(len(assigned_drones), 1)

    def test_15_invalid_telemetry(self):
        packages = {
            1: self._create_package(1, 1.0, 500.0, float('nan'), 0),
            2: self._create_package(2, 1.0, 500.0, 4500, 0)
        }
        drones = {
            1: self._create_drone(1, status="IDLE", battery=-5.0),
            2: self._create_drone(2, status="IDLE", battery=100.0)
        }
        pads = {1: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        self.assertEqual(packages[1].status, "REJECTED")
        self.assertEqual(packages[2].assigned_drone, 2)
        
    def test_16_battery_degradation(self):
        packages = {
            1: self._create_package(1, 1.0, 500.0, 4500, 0)
        }
        drones = {
            1: self._create_drone(1, status="IDLE"),
            2: self._create_drone(2, status="IDLE")
        }
        
        drones[1].battery_capacity = 80.0
        drones[1].battery = 80.0
        
        matrix, _ = assignment.build_cost_matrix(drones, packages, 0.0, "v1", {})
        
        c1 = next(c for c in matrix[1]["candidates"] if c["drone_id"] == 1)
        c2 = next(c for c in matrix[1]["candidates"] if c["drone_id"] == 2)
        
        self.assertTrue(c1["features"]["energy_cost"] > c2["features"]["energy_cost"])

    def test_17_exact_deadline(self):
        packages = {
            1: self._create_package(1, 1.0, 100.0, 1000, 0),
            2: self._create_package(2, 1.0, 100.0, 1000, 0),
            3: self._create_package(3, 1.0, 100.0, 1000, 0)
        }
        drones = {
            1: self._create_drone(1, status="DELIVERY"),
            2: self._create_drone(2, status="DELIVERY"),
            3: self._create_drone(3, status="DELIVERY")
        }
        
        dt = 1.0
        remaining_dt = 1.0
        
        sim_time_1 = 99.99
        fsm.complete_delivery(drones[1], packages[1], sim_time_1, dt, remaining_dt)
        self.assertEqual(packages[1].status, "DELIVERED_ON_TIME")
        
        sim_time_2 = 100.00
        fsm.complete_delivery(drones[2], packages[2], sim_time_2, dt, remaining_dt)
        self.assertEqual(packages[2].status, "DELIVERED_ON_TIME")
        
        sim_time_3 = 100.01
        fsm.complete_delivery(drones[3], packages[3], sim_time_3, dt, remaining_dt)
        self.assertEqual(packages[3].status, "DELIVERED_LATE")

    def test_18_charging_reservation_disappears_after_abort(self):
        packages = {1: self._create_package(1, 1.0, 500.0, 4500, 0)}
        drones = {1: self._create_drone(1, status="IDLE")}
        pads = {1: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        self.assertEqual(packages[1].assigned_drone, 1)
        
        fsm.abort_mission(drones[1], packages[1], 10.0, "Wind")
        self.assertEqual(drones[1].status, "RETURNING")
        self.assertIsNone(drones[1].charging_pad)

    def test_19_drone_reports_impossible_telemetry_while_idle(self):
        packages = {1: self._create_package(1, 1.0, 500.0, 4500, 0)}
        drones = {1: self._create_drone(1, status="IDLE", battery=200.0)}
        pads = {1: None}
        
        with self.assertRaises(AssertionError):
            simulation.validate_fleet(drones, pads, packages)
        
    def test_20_stress_test(self):
        packages = {i: self._create_package(i, 1.0, 1000.0, 1000*i, 0) for i in range(1, 21)}
        drones = {i: self._create_drone(i) for i in range(1, 11)}
        pads = {1: None, 2: None, 3: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        simulation.validate_fleet(drones, pads, packages)
        
        assigned = sum(1 for p in packages.values() if p.assigned_drone is not None and p.assigned_drone != -1)
        self.assertLessEqual(assigned, 10)

if __name__ == '__main__':
    unittest.main()
