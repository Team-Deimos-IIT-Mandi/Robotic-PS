import sys
import unittest
import itertools
import random
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import assignment
from swarm_drone import simulation
from swarm_drone.drone_sim import BASE, DroneState, PackageState
from swarm_drone.physics import calculate_battery_consumption, calculate_required_battery


class TestPredictiveCharging(unittest.TestCase):
    def drone(self, drone_id, **kwargs):
        return DroneState(id=drone_id, x=float(BASE[0]), y=float(BASE[1]), **kwargs)

    def package(self, package_id=1, **kwargs):
        values = dict(x=float(BASE[0] + 120), y=float(BASE[1]), deadline=1000.0)
        values.update(kwargs)
        return PackageState(id=package_id, **values)

    def returning(self, drone_id, seconds, **kwargs):
        drone = self.drone(drone_id, status="RETURNING", **kwargs)
        drone.x += seconds * 120.0
        drone.target = BASE
        return drone

    def test_earlier_return_occupies_pad(self):
        earlier = self.returning(1, 5.0, battery=10.0)
        candidate = self.returning(2, 10.0, battery=10.0)
        drones = {1: earlier, 2: candidate}
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0, drones, {1: None})
        battery = earlier.battery - calculate_battery_consumption(5.0, 0.0)
        expected = 5.0 + assignment._charge_duration(100.0, battery, 100.0) - 10.0
        self.assertAlmostEqual(wait, expected)

    def test_later_return_does_not_delay_candidate(self):
        later = self.returning(1, 20.0, battery=10.0)
        candidate = self.returning(2, 10.0, battery=10.0)
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             {1: later, 2: candidate}, {1: None})
        self.assertEqual(wait, 0.0)

    def test_three_pads_handle_two_earlier_returns_without_wait(self):
        candidate = self.returning(3, 10.0, battery=10.0)
        drones = {1: self.returning(1, 5.0, battery=10.0),
                  2: self.returning(2, 8.0, battery=10.0), 3: candidate}
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             drones, {1: None, 2: None, 3: None})
        self.assertEqual(wait, 0.0)

    def test_live_charging_occupancy_sets_pad_release_time(self):
        charging = self.drone(1, status="CHARGING", battery=10.0,
                              target_battery=20.0, charging_pad=1)
        candidate = self.returning(2, 10.0, battery=10.0)
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             {1: charging, 2: candidate}, {1: 1})
        self.assertAlmostEqual(wait, 230.0)

    def test_delivery_forecast_uses_remaining_trip(self):
        package = self.package(weight=2.5)
        drone = self.drone(1, status="DELIVERY", battery=50.0, current_package=1, payload=2.5)
        drone.x += 60.0
        reasons = []
        seconds, battery = assignment._project_state_at_base(drone, {1: package}, reasons)
        expected_seconds = 6.0 / 8.4 + 12.0 / 12.0
        expected_energy = (calculate_battery_consumption(6.0 / 8.4, 2.5)
                           + calculate_battery_consumption(1.0, 0.0))
        self.assertEqual(reasons, [])
        self.assertAlmostEqual(seconds, expected_seconds)
        self.assertAlmostEqual(battery, 50.0 - expected_energy)

    def test_earlier_delivery_adds_charging_demand(self):
        package = self.package()
        earlier = self.drone(1, status="DELIVERY", battery=10.0, current_package=1)
        candidate = self.returning(2, 10.0, battery=10.0)
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             {1: earlier, 2: candidate}, {1: None}, {1: package})
        self.assertGreater(wait, 2000.0)

    def test_future_arrival_uses_soft_package_target(self):
        package = self.package()
        earlier = self.returning(1, 5.0, battery=10.0, preparation_package=1)
        candidate = self.returning(2, 10.0, battery=10.0)
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             {1: earlier, 2: candidate}, {1: None}, {1: package})
        battery = earlier.battery - calculate_battery_consumption(5.0, 0.0)
        target = calculate_required_battery(self.drone(0), package) + 11.0
        self.assertAlmostEqual(wait, 5.0 + assignment._charge_duration(100.0, battery, target) - 10.0)
        self.assertLess(wait, 100.0)

    def test_ready_future_drone_does_not_reserve_pad(self):
        earlier = self.returning(1, 5.0, battery=80.0)
        candidate = self.returning(2, 10.0, battery=10.0)
        wait = assignment._candidate_pad_wait(candidate, 10.0, 9.0, 20.0,
                                             {1: earlier, 2: candidate}, {1: None})
        self.assertEqual(wait, 0.0)

    def test_existing_waiters_keep_fifo_order(self):
        later = self.drone(1, status="WAITING_FOR_CHARGE", battery=0.0,
                           target_battery=50.0, wait_start_time=9.0)
        candidate = self.drone(2, status="WAITING_FOR_CHARGE", battery=0.0,
                               target_battery=10.0, wait_start_time=5.0)
        wait = assignment._candidate_pad_wait(candidate, 0.0, 0.0, 10.0,
                                             {1: later, 2: candidate}, {1: None}, sim_time=10.0)
        self.assertEqual(wait, 0.0)

    def test_live_waiters_start_in_fifo_order(self):
        later = self.drone(1, status="WAITING_FOR_CHARGE", battery=0.0,
                           target_battery=50.0, wait_start_time=9.0)
        earlier = self.drone(2, status="WAITING_FOR_CHARGE", battery=0.0,
                             target_battery=10.0, wait_start_time=5.0)
        pads = {1: None}
        assignment._execute_v3_charging({1: later, 2: earlier}, {}, 10.0, pads, 0.11)
        self.assertEqual(pads[1], 2)
        self.assertEqual(later.status, "WAITING_FOR_CHARGE")

    def test_stale_soft_plan_does_not_start_idle_charging(self):
        drone = self.drone(1, battery=50.0, preparation_package=1)
        package = self.package(status="REJECTED", assigned_drone=-1)
        pads = {1: None}
        assignment._execute_v3_charging({1: drone}, {1: package}, 10.0, pads, 0.11)
        self.assertEqual(drone.status, "IDLE")
        self.assertIsNone(drone.preparation_package)
        self.assertIsNone(pads[1])

    def test_aborted_return_keeps_payload_in_physics(self):
        drone = self.returning(1, 10.0, battery=50.0, payload=2.5)
        seconds, battery = assignment._project_state_at_base(drone, {}, [])
        self.assertAlmostEqual(seconds, 120.0 / 8.4)
        self.assertAlmostEqual(battery, 50.0 - calculate_battery_consumption(seconds, 2.5))

    def test_configurable_reserve_and_actual_launch_battery(self):
        package = self.package()
        drone = self.drone(1, battery=80.0)
        candidate = assignment.candidate_details(drone, package, 0.0, ("IDLE",),
                                                 reserve_fraction=0.20)
        self.assertAlmostEqual(candidate["target_battery"], candidate["required_energy"] + 20.0)
        features = assignment.calculate_predictive_assignment_features(drone, package, candidate, 0.0)
        self.assertEqual(features["predicted_battery_after_charge"], 80.0)
        for reserve in (-0.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                assignment.schedule_packages({}, {}, 0.0, {}, "v3", reserve_fraction=reserve)

    def test_v3_charges_then_dispatches_without_v2_planner(self):
        drone = self.drone(1, battery=0.0)
        package = self.package()
        drones, packages, pads = {1: drone}, {1: package}, {1: None}
        with patch("swarm_drone.assignment_algorithms.v2.manage_charging_infrastructure",
                   side_effect=AssertionError("V2 planner called")):
            assignment.schedule_packages(drones, packages, 0.0, pads, "v3", reserve_fraction=0.15)
            self.assertEqual(package.status, "PENDING")
            self.assertIsNone(package.assigned_drone)
            self.assertEqual(drone.status, "CHARGING")
            self.assertAlmostEqual(drone.target_battery, calculate_required_battery(self.drone(0), package) + 15.0)
            for tick in range(1, 500):
                simulation.run_simulation_step(drone, packages, 1.0, tick - 1.0, pads)
                assignment.schedule_packages(drones, packages, float(tick), pads, "v3", reserve_fraction=0.15)
                simulation.validate_fleet(drones, pads, packages)
                if package.delivered:
                    break
        self.assertEqual(package.status, "DELIVERED_ON_TIME")

    def test_busy_selection_does_not_assign_second_package(self):
        current = self.package(1, status="ASSIGNED", assigned_drone=1)
        pending = self.package(2)
        drone = self.drone(1, status="DELIVERY", battery=80.0, current_package=1)
        drone.target = (current.x, current.y)
        assignment.schedule_packages({1: drone}, {1: current, 2: pending}, 0.0, {1: None}, "v3")
        self.assertEqual(drone.current_package, 1)
        self.assertEqual(pending.status, "PENDING")
        self.assertIsNone(pending.assigned_drone)
        self.assertEqual(drone.preparation_package, 2)

    def test_unknown_pad_owner_blocks_forecast(self):
        drone = self.drone(1, battery=0.0)
        wait = assignment._candidate_pad_wait(drone, 0.0, 0.0, 20.0, {1: drone}, {1: 99})
        self.assertEqual(wait, float("inf"))

    def test_nonurgent_burst_preserves_two_usable_drones(self):
        drones = {i: self.drone(i, battery=80.0) for i in range(1, 5)}
        packages = {i: self.package(i) for i in range(1, 5)}
        assignment.schedule_packages(drones, packages, 0.0, {1: None}, "v3")
        self.assertEqual(sum(p.status == "ASSIGNED" for p in packages.values()), 2)
        self.assertEqual(sum(d.status == "IDLE" for d in drones.values()), 2)
        self.assertTrue(all(p.assigned_drone is None for p in packages.values() if p.status == "PENDING"))

    def test_urgent_burst_can_consume_reserve(self):
        drones = {i: self.drone(i, battery=80.0) for i in range(1, 5)}
        packages = {i: self.package(i, deadline=2.0) for i in range(1, 5)}
        assignment.schedule_packages(drones, packages, 0.0, {1: None}, "v3")
        self.assertTrue(all(p.status == "ASSIGNED" for p in packages.values()))

    def test_reserve_can_be_disabled(self):
        drones = {i: self.drone(i, battery=80.0) for i in range(1, 5)}
        packages = {i: self.package(i) for i in range(1, 5)}
        assignment.schedule_packages(drones, packages, 0.0, {1: None}, "v3", min_reserve=0)
        self.assertTrue(all(p.status == "ASSIGNED" for p in packages.values()))

    def test_urgent_dispatch_reduces_normal_dispatch_budget(self):
        drones = {i: self.drone(i, battery=80.0) for i in range(1, 5)}
        packages = {1: self.package(1, deadline=2.0),
                    2: self.package(2), 3: self.package(3), 4: self.package(4)}
        assignment.schedule_packages(drones, packages, 0.0, {1: None}, "v3")
        self.assertEqual(packages[1].status, "ASSIGNED")
        self.assertEqual(sum(p.status == "ASSIGNED" for p in packages.values()), 2)

    def test_saturated_return_charging_defers_only_nonurgent_mission(self):
        drones = {1: self.drone(1, battery=15.0),
                  2: self.drone(2, status="CHARGING", battery=0.0, charging_pad=1),
                  3: self.drone(3, status="WAITING_FOR_CHARGE", battery=0.0),
                  4: self.drone(4, status="WAITING_FOR_CHARGE", battery=0.0)}
        pads = {1: 2}
        package = self.package()
        matrix, _ = assignment.build_cost_matrix(drones, {1: package}, 0.0, "v3", charging_pads=pads)
        candidate = matrix[1]["all_candidates_log"][0]
        self.assertTrue(candidate["needs_return_charging"])
        self.assertGreater(candidate["return_pad_wait"], assignment.MAX_RETURN_PAD_WAIT)
        self.assertIn("Fleet saturated", candidate["policy_reason"])
        self.assertNotIn(candidate, matrix[1]["candidates"])
        package.deadline = 2.0
        matrix, _ = assignment.build_cost_matrix(drones, {1: package}, 0.0, "v3", charging_pads=pads)
        candidate = matrix[1]["all_candidates_log"][0]
        self.assertTrue(candidate["urgent"])
        self.assertIsNone(candidate["policy_reason"])
        self.assertIn(candidate, matrix[1]["candidates"])

    def test_return_collision_penalty_depends_on_charging_need(self):
        package = self.package()
        other = self.returning(2, 2.0, battery=10.0)
        low = self.drone(1, battery=15.0)
        candidate = assignment.candidate_details(low, package, 0.0, ("IDLE",),
                                                 drones={1: low, 2: other}, charging_pads={1: None})
        self.assertEqual(candidate["predicted_return_time"], 2.0)
        self.assertEqual(candidate["return_collisions"], 1)
        self.assertGreater(candidate["return_collision_cost"], 0.0)
        low.battery = 80.0
        candidate = assignment.candidate_details(low, package, 0.0, ("IDLE",),
                                                 drones={1: low, 2: other}, charging_pads={1: None})
        self.assertEqual(candidate["return_collision_cost"], 0.0)

    def test_v3_cost_ranking_is_effective_before_slack_tiebreak(self):
        package = self.package()
        candidates = [{"drone_id": 1, "slack": 80.0, "cost": 10.0},
                      {"drone_id": 2, "slack": 60.0, "cost": 1.0}]
        matrix = {1: {"candidates": candidates}}
        legacy = assignment.find_max_coverage_assignment(matrix, [package])
        predictive = assignment.find_max_coverage_assignment(matrix, [package], cost_first=True)
        self.assertEqual(legacy[0][1]["drone_id"], 1)
        self.assertEqual(predictive[0][1]["drone_id"], 2)

    def test_slow_candidate_does_not_make_a_nonurgent_package_urgent(self):
        drones = {1: self.drone(1, battery=80.0),
                  2: self.drone(2, status="CHARGING", battery=10.0, charging_pad=1)}
        package = self.package(deadline=40.0)
        matrix, _ = assignment.build_cost_matrix(drones, {1: package}, 0.0, "v3", charging_pads={1: 2})
        self.assertTrue(all(not c["urgent"] for c in matrix[1]["candidates"]))
        result = assignment.find_max_coverage_assignment(matrix, [package], cost_first=True)
        self.assertEqual(result[0][1]["drone_id"], 1)

    def test_small_fleet_and_failed_drones_do_not_lock_reserve(self):
        drone = self.drone(1, battery=80.0)
        failed = self.drone(2, status="FAILED", battery=0.0)
        package = self.package()
        assignment.schedule_packages({1: drone, 2: failed}, {1: package}, 0.0, {1: None}, "v3")
        self.assertEqual(package.assigned_drone, 1)
        for reserve in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                assignment.schedule_packages({}, {}, 0.0, {}, "v3", min_reserve=reserve)

    def test_policy_search_matches_exhaustive_small_assignments(self):
        rng = random.Random(17)
        packages = [self.package(i) for i in range(1, 5)]
        for _ in range(10):
            matrix = {}
            for package in packages:
                matrix[package.id] = {"candidates": [
                    {"drone_id": drone_id, "cost": rng.uniform(0.0, 10.0),
                     "slack": rng.uniform(1.0, 100.0), "urgent": package.id == 1,
                     "requires_dispatch": drone_id <= 2}
                    for drone_id in range(1, 4)
                ]}
            best = None
            for choices in itertools.product(*(
                    [None] + matrix[p.id]["candidates"] for p in packages)):
                selected = [c for c in choices if c is not None]
                if len({c["drone_id"] for c in selected}) != len(selected):
                    continue
                departures = sum(c["requires_dispatch"] for c in selected)
                normal_departures = sum(c["requires_dispatch"] and not c["urgent"] for c in selected)
                if normal_departures and departures > 1:
                    continue
                key = (-len(selected), -sum(c["urgent"] for c in selected),
                       sum(c["cost"] for c in selected),
                       -min((c["slack"] for c in selected), default=-float("inf")),
                       -sum(c["slack"] for c in selected))
                if best is None or key < best:
                    best = key
            result = assignment.find_max_coverage_assignment(
                matrix, packages, dispatch_budget=1, cost_first=True)
            selected = [c for _, c in result]
            actual = (-len(selected), -sum(c["urgent"] for c in selected),
                      sum(c["cost"] for c in selected),
                      -min((c["slack"] for c in selected), default=-float("inf")),
                      -sum(c["slack"] for c in selected))
            self.assertEqual(actual, best)


if __name__ == "__main__":
    unittest.main()
