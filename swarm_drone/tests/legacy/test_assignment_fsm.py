import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from swarm_drone import simulation as s
from swarm_drone.drone_sim import BASE, PackageState


class AssignmentFSMTests(unittest.TestCase):
    def package(self, id=1, distance=840, deadline=1000, weight=2.5, request_time=0):
        return PackageState(id, BASE[0]+distance, BASE[1], weight=weight,
                            deadline=deadline, request_time=request_time)

    def step(self, drones, packages, pads, now, dt=1):
        s.assign_packages_fsm(drones, packages, now, pads, dt)
        for drone in drones.values():
            s.run_simulation_step(drone, packages, dt, now, pads)
        s.validate_fleet(drones, pads, packages)

    def test_old_policies_can_assign_again(self):
        for policy in (s.assign_packages_baseline, s.assign_packages_v1, s.assign_packages_v2):
            with self.subTest(policy=policy.__name__):
                drones, package = s.initialize_drones(1), self.package()
                policy(drones, {1:package}, 0, {1:None})
                self.assertEqual(package.assigned_drone, 1)

    def test_fsm_never_calls_weighted_scores_or_v2_beam(self):
        with (patch.object(s, 'calculate_assignment_score', side_effect=AssertionError('V1 score')),
             patch.object(s, 'calculate_assignment_score_v2', side_effect=AssertionError('V2 score')),
             patch.object(s, 'plan_fleet_preparation', side_effect=AssertionError('V2 planner'))):
            drones, package = s.initialize_drones(2), self.package()
            s.schedule_packages(drones, {1:package}, 0, {}, 'fsm')
            self.assertIsNotNone(package.assigned_drone)
            self.assertEqual(len(package.decision_history[-1]['proposals']), 2)

    def test_explicit_transition_trace(self):
        drones, package = s.initialize_drones(1), self.package()
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        log = package.decision_history[-1]
        self.assertEqual(log['event'], 'SCHEDULER_TICK')
        self.assertEqual([t['next'] for t in log['transitions']],
                         ['CHECK_FEASIBILITY', 'CHECK_READINESS', 'CHECK_URGENCY', 'SELECT_DRONE', 'ASSIGN'])
        for change in log['transitions']:
            self.assertIn(s.AssignmentState[change['next']], s.ASSIGNMENT_TRANSITIONS[s.AssignmentState[change['previous']]])
        json.dumps(log, allow_nan=False)

    def test_slack_subtracts_travel_time(self):
        drones, package = s.initialize_drones(1), self.package(distance=4620, deadline=60)
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertAlmostEqual(package.decision_history[-1]['slack_seconds'], 5)

    def test_critical_uses_tick_not_twenty_second_threshold(self):
        drones, package = s.initialize_drones(1), self.package(distance=4956, deadline=60)
        s.assign_packages_fsm(drones, {1:package}, 0, {}, timestep=1)
        self.assertEqual(package.decision_history[-1]['urgency'], 'CRITICAL')

    def test_package_order_uses_spare_time_not_just_deadline(self):
        drones = s.initialize_drones(1)
        packages = {1:self.package(1,840,30), 2:self.package(2,4620,60)}
        s.assign_packages_fsm(drones,packages,0,{})
        self.assertEqual(packages[2].assigned_drone,1)
        self.assertIsNone(packages[1].assigned_drone)

    def test_charging_drone_can_leave_with_safe_energy(self):
        drones, package = s.initialize_drones(1), self.package()
        drones[1].battery = 15
        drones[1].status, drones[1].charging_pad = 'CHARGING', 1
        pads = {1:1}
        s.assign_packages_fsm(drones, {1:package}, 0, pads)
        self.assertEqual(package.assigned_drone, 1)
        self.assertEqual(pads, {1:None})
        self.assertEqual(drones[1].battery, 15)
        s.validate_fleet(drones, pads, {1:package})

    def test_common_reserve_is_not_relaxed(self):
        drones, package = s.initialize_drones(1), self.package()
        drones[1].battery = s.mission_departure_energy(drones[1], package)-.01
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertIsNone(package.assigned_drone)
        self.assertEqual(package.status, 'PENDING')

    def test_charge_then_retry_and_deliver(self):
        drones, package = s.initialize_drones(1), self.package(distance=4200, deadline=180)
        drones[1].battery = 12
        pads, packages = {1:None}, {1:package}
        s.assign_packages_fsm(drones, packages, 0, pads)
        self.assertEqual(package.decision_history[-1]['fsm_state'], 'WAIT')
        self.assertEqual(package.decision_history[-1]['prepared_drone'], 1)
        self.assertIsNone(package.assigned_drone)
        self.assertAlmostEqual(drones[1].target_battery, s.mission_departure_energy(drones[1], package))
        for now in range(180):self.step(drones, packages, pads, now)
        self.assertEqual(package.status, 'DELIVERED_ON_TIME')
        self.assertTrue(any(any(t['next']=='PREPARE' for t in e.get('transitions', []))
                            for e in package.decision_history))

    def test_quarter_second_playback_step_keeps_safe_timing(self):
        drones, package = s.initialize_drones(1), self.package(distance=4200,deadline=122)
        drones[1].battery = 12
        pads = {1:None}
        for tick in range(492):self.step(drones,{1:package},pads,tick*.25,.25)
        self.assertEqual(package.status,'DELIVERED_ON_TIME')
        self.assertLessEqual(package.delivered_at,122)

    def test_wait_ends_when_deadline_is_no_longer_possible(self):
        drones, package = s.initialize_drones(1), self.package(deadline=20)
        drones[1].battery = 1
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertEqual(package.status, 'PENDING')
        s.assign_packages_fsm(drones, {1:package}, 11, {})
        self.assertEqual(package.status, 'REJECTED')
        self.assertEqual(package.decision_history[-1]['fsm_state'], 'REJECT')

    def test_already_expired_request_is_separate_outcome(self):
        package = self.package(deadline=1)
        s.assign_packages_fsm(s.initialize_drones(1), {1:package}, 2, {})
        self.assertEqual(package.status, 'EXPIRED')
        self.assertEqual(package.decision_history[-1]['fsm_state'], 'EXPIRED')

    def test_invalid_and_overweight_requests_rejected(self):
        for weight in (3, -1, float('nan')):
            with self.subTest(weight=weight):
                package = self.package(weight=weight)
                s.assign_packages_fsm(s.initialize_drones(1), {1:package}, 0, {})
                self.assertEqual(package.status, 'REJECTED')
                self.assertEqual(package.assigned_drone, -1)

    def test_future_request_is_not_used(self):
        package = self.package(request_time=100)
        drones = s.initialize_drones(1)
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertIsNone(package.assigned_drone)
        self.assertEqual(package.decision_history, [])

    def test_two_packages_cannot_claim_one_drone(self):
        drones = s.initialize_drones(1)
        packages = {1:self.package(1), 2:self.package(2, deadline=20)}
        s.assign_packages_fsm(drones, packages, 0, {})
        self.assertEqual(packages[2].assigned_drone, 1)
        self.assertIsNone(packages[1].assigned_drone)
        self.assertEqual(packages[1].decision_history[-1]['fsm_state'], 'WAIT')
        s.validate_fleet(drones, {}, packages)

    def test_duplicate_tick_cannot_assign_same_package_twice(self):
        drones, package = s.initialize_drones(2), self.package()
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        owner = package.assigned_drone
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertEqual(package.assigned_drone, owner)
        self.assertEqual(sum(d.current_package==1 for d in drones.values()), 1)

    def test_preserves_only_drone_that_can_serve_another_job(self):
        drones = s.initialize_drones(2)
        drones[1].battery, drones[2].battery = 30, 12
        packages = {1:self.package(1,840,20), 2:self.package(2,4200,100)}
        s.assign_packages_fsm(drones, packages, 0, {})
        self.assertEqual(packages[1].assigned_drone, 2)
        self.assertEqual(packages[2].assigned_drone, 1)

    def test_least_used_breaks_equal_ready_drone_tie(self):
        drones, package = s.initialize_drones(2), self.package()
        drones[1].total_flight_time = 100
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertEqual(package.assigned_drone, 2)

    def test_airborne_drone_is_forecast_but_not_dispatched_or_teleported(self):
        drones, package = s.initialize_drones(1), self.package()
        drone = drones[1]
        drone.x += 1200
        drone.status, drone.target = 'RETURNING', BASE
        before = (drone.x, drone.y, drone.battery, drone.status, drone.target)
        s.assign_packages_fsm(drones, {1:package}, 0, {1:None})
        self.assertEqual((drone.x, drone.y, drone.battery, drone.status, drone.target), before)
        self.assertIsNone(package.assigned_drone)
        self.assertEqual(package.decision_history[-1]['preparation']['available_at'], 10)

    def test_no_pad_means_wait_not_unsafe_launch(self):
        drones, package = s.initialize_drones(1), self.package()
        drones[1].battery = 5
        s.assign_packages_fsm(drones, {1:package}, 0, {})
        self.assertIsNone(package.assigned_drone)
        self.assertEqual(package.decision_history[-1]['fsm_state'], 'WAIT')

    def test_two_future_charges_never_overlap_on_one_pad(self):
        drones = s.initialize_drones(2)
        for drone in drones.values():drone.battery = 10
        packages = {i:self.package(i,4200) for i in (1,2)}
        pads = {1:None}
        s.assign_packages_fsm(drones, packages, 0, pads)
        plans = [p.decision_history[-1]['preparation'] for p in packages.values()]
        self.assertEqual(len({p['drone_id'] for p in plans}), 2)
        slots = sorted((p['charge_start'],p['charge_end']) for p in plans)
        self.assertLessEqual(slots[0][1], slots[1][0])
        s.validate_simulation(drones,pads)

    def test_spare_charging_yields_to_returning_drone_reservation(self):
        drones, package = s.initialize_drones(2), self.package(distance=4200,deadline=180)
        drones[1].battery = 12
        drones[1].x += 1200
        drones[1].status, drones[1].target = 'RETURNING',BASE
        drones[2].battery = 1
        pads = {1:None}
        s.assign_packages_fsm(drones,{1:package},0,pads)
        self.assertEqual(pads[1],2)
        self.assertEqual(drones[2].charging_basis['yield_by'],10)
        for now in range(10):self.step(drones,{1:package},pads,now)
        s.assign_packages_fsm(drones,{1:package},10,pads)
        self.assertEqual(pads[1],1)
        self.assertIsNone(drones[2].charging_pad)
        s.validate_simulation(drones,pads)

    def test_recovery_targets_mission_not_fixed_twenty_percent(self):
        drones, package = s.initialize_drones(1), self.package(distance=4200,deadline=780)
        drones[1].battery, drones[1].low_battery_wait_since = 12,0
        pads = {1:None}
        s.assign_packages_fsm(drones, {1:package}, 600, pads)
        self.assertEqual(drones[1].recovery_package, 1)
        self.assertLess(drones[1].target_battery, 20)
        self.assertEqual(package.decision_history[-1]['prepared_drone'], 1)
        for now in range(600,781):self.step(drones,{1:package},pads,now)
        self.assertEqual(package.status,'DELIVERED_ON_TIME')

    def test_recovery_without_work_keeps_fallback(self):
        drones = s.initialize_drones(1)
        drones[1].battery, drones[1].low_battery_wait_since = 10,0
        pads = {1:None}
        s.assign_packages_fsm(drones, {}, 600, pads)
        self.assertEqual(drones[1].target_battery, 20)
        self.assertEqual(pads[1], 1)

    def test_invalidated_preparation_releases_package_pairing(self):
        drones, package = s.initialize_drones(1), self.package(distance=4200)
        drones[1].battery = 12
        pads = {1:None}
        s.assign_packages_fsm(drones,{1:package},0,pads)
        package.status, package.assigned_drone = 'REJECTED',-1
        s.assign_packages_fsm(drones,{1:package},1,pads)
        self.assertIsNone(drones[1].preparation_package)
        self.assertIsNone(drones[1].recovery_package)

    def test_invalid_battery_is_not_a_candidate(self):
        drones, package = s.initialize_drones(2), self.package()
        drones[1].battery = float('nan')
        s.assign_packages_fsm(drones,{1:package},0,{})
        self.assertEqual(package.assigned_drone, 2)

    def test_bad_timestep_rejected(self):
        for timestep in (0,-1,float('nan')):
            with self.assertRaises(ValueError):
                s.assign_packages_fsm({}, {}, 0, {}, timestep)

    def test_replay_is_deterministic(self):
        snapshots=[]
        for _ in range(2):
            drones=s.initialize_drones(2)
            for drone in drones.values():drone.battery=13
            packages={i:self.package(i,2100+i*100,500) for i in (1,2,3)}
            pads={1:None}
            for now in range(300):self.step(drones,packages,pads,now)
            snapshots.append(copy.deepcopy((drones,packages,pads)))
        self.assertEqual(snapshots[0],snapshots[1])


if __name__ == '__main__':
    unittest.main()
