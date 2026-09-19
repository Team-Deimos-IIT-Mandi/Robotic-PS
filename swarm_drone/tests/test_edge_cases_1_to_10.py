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
class TestEdgeCases(unittest.TestCase):
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

    def test_1_impossible_deadline(self):
        # Package P1: deadline = 5s, drop distance = 100m.
        packages = {1: self._create_package(1, weight=1.0, deadline=5.0, dx=1000.0, dy=0.0)}
        drones = {1: self._create_drone(1)}
        pads = {1: None, 2: None, 3: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        self.assertEqual(packages[1].status, "REJECTED")
        self.assertIn("Even immediate departure cannot meet deadline", packages[1].outcome_reason)
        self.assertEqual(packages[1].assigned_drone, -1)
        self.assertEqual(drones[1].status, "IDLE")

    def test_2_overweight_package(self):
        packages = {
            1: self._create_package(1, weight=3.0, deadline=500.0, dx=100.0, dy=0.0),
            2: self._create_package(2, weight=2.5, deadline=500.0, dx=100.0, dy=0.0),
            3: self._create_package(3, weight=2.501, deadline=500.0, dx=100.0, dy=0.0)
        }
        drones = {1: self._create_drone(1)}
        pads = {1: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        self.assertEqual(packages[1].status, "REJECTED")
        self.assertEqual(packages[3].status, "REJECTED")
        self.assertNotEqual(packages[2].status, "REJECTED")

    def test_3_max_coverage_beats_lowest_cost(self):
        packages = {
            1: self._create_package(1, 1.0, 100, 100, 0),
            2: self._create_package(2, 1.0, 100, 100, 0),
            3: self._create_package(3, 1.0, 100, 100, 0)
        }
        
        matrix = {
            1: {
                "package": packages[1],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 2},
                    {"drone_id": 2, "slack": 50, "cost": 4},
                ]
            },
            2: {
                "package": packages[2],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 4},
                ]
            },
            3: {
                "package": packages[3],
                "candidates": [
                    {"drone_id": 2, "slack": 50, "cost": 2},
                    {"drone_id": 3, "slack": 50, "cost": 4},
                ]
            }
        }
        pending = list(packages.values())
        best = assignment.find_max_coverage_assignment(matrix, pending)
        
        self.assertEqual(len(best), 3)
        assigned_pairs = {(p.id, c["drone_id"]) for p, c in best}
        self.assertEqual(assigned_pairs, {(1, 2), (2, 1), (3, 3)})

    def test_4_one_drone_two_packages(self):
        packages = {
            1: self._create_package(1, 1.0, 100, 100, 0),
            2: self._create_package(2, 1.0, 100, 100, 0)
        }
        matrix = {
            1: {
                "package": packages[1],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 10},
                ]
            },
            2: {
                "package": packages[2],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 5},
                    {"drone_id": 2, "slack": 50, "cost": 20},
                ]
            }
        }
        pending = list(packages.values())
        best = assignment.find_max_coverage_assignment(matrix, pending)
        
        self.assertEqual(len(best), 2)
        assigned_pairs = {(p.id, c["drone_id"]) for p, c in best}
        self.assertEqual(assigned_pairs, {(1, 1), (2, 2)})

    def test_5_reverse_package_order(self):
        packages = {
            1: self._create_package(1, 1.0, 100, 100, 0),
            2: self._create_package(2, 1.0, 100, 100, 0)
        }
        matrix = {
            1: {
                "package": packages[1],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 10},
                ]
            },
            2: {
                "package": packages[2],
                "candidates": [
                    {"drone_id": 1, "slack": 50, "cost": 5},
                    {"drone_id": 2, "slack": 50, "cost": 20},
                ]
            }
        }
        pending = [packages[2], packages[1]] # Reversed
        best = assignment.find_max_coverage_assignment(matrix, pending)
        
        self.assertEqual(len(best), 2)
        assigned_pairs = {(p.id, c["drone_id"]) for p, c in best}
        self.assertEqual(assigned_pairs, {(1, 1), (2, 2)})

    def test_6_urgency_breaks_tie(self):
        packages = {
            1: self._create_package(1, 1.0, 100, 100, 0),
            2: self._create_package(2, 1.0, 100, 100, 0)
        }
        matrix = {
            1: {
                "package": packages[1],
                "candidates": [
                    {"drone_id": 1, "slack": 10, "cost": 10}, # A
                    {"drone_id": 2, "slack": 40, "cost": 10}, # B
                ]
            },
            2: {
                "package": packages[2],
                "candidates": [
                    {"drone_id": 2, "slack": 100, "cost": 10}, # A
                    {"drone_id": 3, "slack": 50, "cost": 10},  # B
                ]
            }
        }
        pending = list(packages.values())
        best = assignment.find_max_coverage_assignment(matrix, pending)
        
        assigned_pairs = {(p.id, c["drone_id"]) for p, c in best}
        self.assertEqual(assigned_pairs, {(1, 2), (2, 3)})

    def test_7_more_packages_than_drones(self):
        packages = {i: self._create_package(i, 1.0, 1000, 100, 0) for i in range(1, 16)}
        drones = {i: self._create_drone(i) for i in range(1, 11)}
        pads = {1: None, 2: None, 3: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        assigned = [p for p in packages.values() if p.assigned_drone is not None and p.assigned_drone != -1]
        pending = [p for p in packages.values() if p.status == "PENDING"]
        
        self.assertEqual(len(assigned), 10)
        self.assertEqual(len(pending), 5)

    def test_8_all_drones_committed(self):
        packages = {1: self._create_package(1, 1.0, 1000, 100, 0)}
        drones = {i: self._create_drone(i, status="DELIVERY") for i in range(1, 11)}
        pads = {1: None, 2: None, 3: None}
        
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        self.assertEqual(packages[1].status, "PENDING")
        self.assertIsNone(packages[1].assigned_drone)
        
        drones[1].status = "IDLE"
        assignment.schedule_packages(drones, packages, 0.0, pads, "v2")
        
        self.assertEqual(packages[1].status, "ASSIGNED")
        self.assertEqual(packages[1].assigned_drone, 1)

    def test_9_all_charging_pads_occupied(self):
        packages = {}
        drones = {
            1: self._create_drone(1, status="CHARGING", charging_pad=1),
            2: self._create_drone(2, status="CHARGING", charging_pad=2),
            3: self._create_drone(3, status="CHARGING", charging_pad=3),
            4: self._create_drone(4, status="RETURNING", battery=10.0)
        }
        pads = {1: 1, 2: 2, 3: 3}
        
        fsm.return_to_base(drones[4], packages, 0.0)
        self.assertEqual(drones[4].status, "WAITING_FOR_CHARGE")
        
        pads[1] = None
        drones[1].status = "IDLE"
        drones[1].charging_pad = None
        
        simulation.update_drone(drones[4], packages, 1.0, pads, 0.0)
        
        self.assertEqual(drones[4].status, "CHARGING")
        self.assertEqual(drones[4].charging_pad, 1)

    def test_10_low_battery_drones_arrive_together(self):
        packages = {}
        drones = {
            1: self._create_drone(1, status="RETURNING", battery=10.0),
            2: self._create_drone(2, status="RETURNING", battery=11.0),
            3: self._create_drone(3, status="RETURNING", battery=12.0),
            4: self._create_drone(4, status="RETURNING", battery=13.0)
        }
        pads = {1: None, 2: None, 3: None}
        
        for i in range(1, 5):
            fsm.return_to_base(drones[i], packages, 0.0)
            
        for i in range(1, 5):
            self.assertEqual(drones[i].status, "WAITING_FOR_CHARGE")
            
        for i in range(1, 5):
            simulation.update_drone(drones[i], packages, 1.0, pads, 0.0)
            
        charging = [d for d in drones.values() if d.status == "CHARGING"]
        waiting = [d for d in drones.values() if d.status == "WAITING_FOR_CHARGE"]
        
        self.assertEqual(len(charging), 3)
        self.assertEqual(len(waiting), 1)

if __name__ == '__main__':
    unittest.main()
