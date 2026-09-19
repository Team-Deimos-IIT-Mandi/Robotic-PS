import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import assignment
from swarm_drone.assignment_algorithms import baseline, v1, v2, v3
from swarm_drone.drone_sim import BASE, DroneState, PackageState
from swarm_drone.physics import calculate_required_battery


class TestAssignmentModules(unittest.TestCase):
    def fleet(self):
        drones = {i: DroneState(id=i, x=float(BASE[0]), y=float(BASE[1]), battery=80.0)
                  for i in range(1, 5)}
        packages = {i: PackageState(id=i, x=float(BASE[0] + 120), y=float(BASE[1]),
                                    deadline=2.0 if i == 1 else 1000.0)
                    for i in range(1, 5)}
        return drones, packages, {1: None, 2: None}

    def test_each_algorithm_has_its_own_scheduler(self):
        self.assertEqual(set(assignment.ALGORITHMS), {"baseline", "v1", "v2", "v3"})
        for name, module in assignment.ALGORITHMS.items():
            with self.subTest(algorithm=name):
                self.assertEqual(module.__name__, "swarm_drone.assignment_algorithms." + name)
                self.assertEqual(module.schedule_packages.__module__, module.__name__)

    def test_direct_schedulers_match_existing_entry_point(self):
        for name, module in assignment.ALGORITHMS.items():
            with self.subTest(algorithm=name):
                direct = self.fleet()
                routed = copy.deepcopy(direct)
                module.schedule_packages(direct[0], direct[1], 0.0, direct[2])
                assignment.schedule_packages(routed[0], routed[1], 0.0, routed[2], name)
                self.assertEqual(direct, routed)

    def test_direct_matrices_match_existing_entry_point(self):
        for name, module in assignment.ALGORITHMS.items():
            with self.subTest(algorithm=name):
                drones, packages, pads = self.fleet()
                direct = module.build_cost_matrix(drones, packages, 0.0, charging_pads=pads)
                routed = assignment.build_cost_matrix(drones, packages, 0.0, name, charging_pads=pads)
                self.assertEqual(direct, routed)

    def test_existing_configurable_defaults_still_work(self):
        drones, packages, pads = self.fleet()
        with patch.object(assignment, "MIN_RESERVE", 0):
            assignment.schedule_packages(drones, packages, 0.0, pads, "v3")
        self.assertTrue(all(p.status == "ASSIGNED" for p in packages.values()))
        drones, packages, pads = self.fleet()
        for drone in drones.values():
            drone.battery = 0.0
        with patch.object(assignment, "RESERVE_FRACTION", 0.20):
            matrix, _ = assignment.build_cost_matrix(drones, packages, 0.0, "v3", charging_pads=pads)
        ideal = DroneState(id=0, x=float(BASE[0]), y=float(BASE[1]))
        expected = calculate_required_battery(ideal, packages[2]) + 20.0
        self.assertAlmostEqual(matrix[2]["all_candidates_log"][0]["target_battery"], expected)

    def test_unknown_algorithm_has_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown assignment algorithm"):
            assignment.schedule_packages({}, {}, 0.0, {}, "missing")


if __name__ == "__main__":
    unittest.main()
