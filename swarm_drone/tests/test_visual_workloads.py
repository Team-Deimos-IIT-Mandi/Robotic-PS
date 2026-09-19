import unittest

from scripts.run_v3_hard_visual import make_workload
from swarm_drone.drone_sim import MAP_W, MAP_H


class TestVisualHardWorkload(unittest.TestCase):
    def test_default_pressure_and_burst_timing(self):
        manifest, batteries = make_workload(40 * 60)
        self.assertEqual(len(manifest), 899)
        self.assertEqual(sum(p.request_time == 0 for p in manifest.values()), 30)
        self.assertEqual(sum(p.request_time == 60 for p in manifest.values()), 11)
        self.assertTrue(all(p.request_time < 2400 for p in manifest.values()))
        self.assertEqual(set(batteries), set(range(1, 11)))
        self.assertEqual((min(batteries.values()), max(batteries.values())), (32, 50))

    def test_reproducible_visible_heavy_requests(self):
        first, _ = make_workload(120, seed=42)
        second, _ = make_workload(120, seed=42)
        different, _ = make_workload(120, seed=43)
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        for package in first.values():
            self.assertTrue(0 < package.x < MAP_W)
            self.assertTrue(0 < package.y < MAP_H)
            self.assertTrue(1.5 <= package.weight <= 2.5)
            self.assertTrue(45 <= package.deadline - package.request_time <= 120)

    def test_custom_pressure_and_empty_manifest(self):
        manifest, _ = make_workload(61, initial_packages=50, arrival_interval=10,
                                    burst_size=20, burst_interval=30)
        self.assertEqual(len(manifest), 96)
        empty, _ = make_workload(1, initial_packages=0, burst_size=0)
        self.assertEqual(empty, {})


if __name__ == "__main__":
    unittest.main()
