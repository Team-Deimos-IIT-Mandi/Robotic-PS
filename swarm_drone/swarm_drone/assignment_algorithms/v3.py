import math
from ..drone_sim import DroneState, BASE
from ..physics import calculate_delivery_time, calculate_required_battery, calculate_mission_distance
from ..fsm import assign_package
from .common import build_matrix, log_deferred, validate_packages
from .optimizer import find_max_coverage_assignment
from .v3_charging import (
    RESERVE_FRACTION, MIN_RESERVE, CRITICAL_SLACK, RETURN_WINDOW, MAX_RETURN_PAD_WAIT,
    WAITING_QUEUE_POLICY, _reserve_fraction, _package_charge_target, _project_state_at_base,
    _charge_duration, _candidate_pad_wait, _return_charging_forecast, _execute_v3_charging,
)

ALLOWED_STATES = ("IDLE", "WAITING_FOR_CHARGE", "CHARGING", "DELIVERY", "RETURNING")


def candidate_details(drone, package, sim_time, allowed, plan=None, algorithm="v3",
                      all_packages=None, drones=None, charging_pads=None,
                      reserve_fraction=None):
    reasons = []
    if drone.status not in allowed:
        reasons.append("Drone unavailable: " + drone.status)

    if drone.status in ("FAILED", "QUARANTINED"):
        reasons.append(f"Drone is {drone.status}")
    if package.weight > 2.5:
        reasons.append("Payload exceeds capacity")

    time_to_base, battery_at_base = _project_state_at_base(drone, all_packages, reasons)

    if battery_at_base < 0:
        reasons.append(f"Drone will fail before reaching base (projected battery: {battery_at_base:.1f})")

    ideal = DroneState(id=0, x=float(BASE[0]), y=float(BASE[1]))
    delivery_time_to_new = calculate_delivery_time(ideal, package)
    required_energy_for_new = calculate_required_battery(ideal, package)

    reserve_fraction = _reserve_fraction(reserve_fraction)
    if required_energy_for_new > drone.battery_capacity + 1e-9:
        reasons.append("Round trip exceeds drone's usable capacity")
    target_battery = _package_charge_target(drone, package, reserve_fraction)
    charge_time = _charge_duration(drone.battery_capacity, battery_at_base, target_battery)
    waiting_for_pad = _candidate_pad_wait(
        drone, time_to_base, battery_at_base, target_battery,
        drones or {drone.id: drone}, charging_pads or {},
        all_packages, sim_time, reserve_fraction,
    )

    dispatch_time = sim_time + time_to_base + waiting_for_pad + charge_time
    arrival = dispatch_time + delivery_time_to_new

    if arrival > package.deadline + 1e-9:
        reasons.append("Predicted arrival after deadline")
    launch_battery = min(drone.battery_capacity, max(battery_at_base, target_battery))
    return_forecast = _return_charging_forecast(
        drone, package, dispatch_time, launch_battery,
        drones or {drone.id: drone}, all_packages, charging_pads or {}, sim_time, reserve_fraction,
    ) if math.isfinite(dispatch_time) else {}
    return {
        "drone_id": drone.id, "status": drone.status, "battery": drone.battery,
        "capacity": drone.battery_capacity, "arrival": arrival,
        "required_energy": required_energy_for_new, "reasons": reasons,
        "slack": package.deadline - arrival,
        "time_to_base": time_to_base, "battery_at_base": battery_at_base,
        "waiting_for_pad": waiting_for_pad,
        "charge_time": charge_time, "dispatch_time": dispatch_time,
        "target_battery": target_battery,
        "predicted_launch_battery": launch_battery,
        "urgent": package.deadline - arrival <= CRITICAL_SLACK,
        **return_forecast,
        "pad_queue_policy": WAITING_QUEUE_POLICY,
    }


def calculate_predictive_assignment_features(drone, package, candidate, sim_time):
    """Predicted dispatch features with historical flight time for balancing."""
    remaining_deadline = max(package.deadline - sim_time, 1e-6)
    predicted_slack = candidate["slack"]
    predicted_launch_battery = candidate["predicted_launch_battery"]
    reserve_after_mission = predicted_launch_battery - candidate["required_energy"]
    reserve_fraction = reserve_after_mission / max(drone.battery_capacity, 1e-6)
    if reserve_fraction > 0.30:
        charging_risk = 0.0
    elif reserve_fraction > 0.15:
        charging_risk = 0.5
    else:
        charging_risk = 1.0

    return {
        "drone_id": drone.id,
        "deadline_cost": 1.0 - predicted_slack / remaining_deadline,
        "energy_cost": candidate["required_energy"] / max(predicted_launch_battery, 1e-6),
        "raw_distance": calculate_mission_distance(
            DroneState(id=0, x=float(BASE[0]), y=float(BASE[1])), package),
        "raw_utilization": drone.total_flight_time,
        "charging_risk": charging_risk,
        "slack": predicted_slack,
        "predicted_dispatch_time": candidate["dispatch_time"],
        "predicted_arrival_time": candidate["arrival"],
        "predicted_slack": predicted_slack,
        "time_to_base": candidate["time_to_base"],
        "battery_at_base": candidate["battery_at_base"],
        "waiting_for_pad": candidate["waiting_for_pad"],
        "charge_time": candidate["charge_time"],
        "predicted_battery_after_charge": predicted_launch_battery,
        "congestion_cost": candidate.get("congestion_cost", 0.0),
        "return_collision_cost": candidate.get("return_collision_cost", 0.0),
        "urgent": candidate.get("urgent", False),
    }


def calculate_predictive_assignment_score(features, max_distance, avg_flight_time, sim_time, deadline):
    """Score predicted timing and energy, with historical workload balancing."""
    remaining_deadline = max(deadline - sim_time, 1e-6)
    normalized_distance = features["raw_distance"] / max(max_distance, 1e-6)
    balance_cost = features["raw_utilization"] / max(avg_flight_time, 1e-6)
    preparation_cost = (
        features["time_to_base"] + features["waiting_for_pad"] + features["charge_time"]
    ) / remaining_deadline
    congestion_penalty = 3.0 * features.get("congestion_cost", 0.0)
    return_penalty = 2.0 * features.get("return_collision_cost", 0.0)
    if features.get("urgent", False):
        congestion_penalty *= 0.25
        return_penalty *= 0.25
    score = (
        10.0 * features["deadline_cost"]
        + 3.0 * features["energy_cost"]
        + normalized_distance
        + 2.0 * balance_cost
        + 2.0 * preparation_cost
        + congestion_penalty
        + return_penalty
    )
    return {
        "score": score,
        "deadline": 10.0 * features["deadline_cost"],
        "energy": 3.0 * features["energy_cost"],
        "distance": normalized_distance,
        "balance": 2.0 * balance_cost,
        "charging": 2.0 * preparation_cost,
        "congestion": congestion_penalty,
        "return_collision": return_penalty,
    }


def build_cost_matrix(drones, packages, sim_time, package_plans=None, charging_pads=None,
                      reserve_fraction=None):
    charging_pads = charging_pads or {}
    def prepare(candidates, package):
        arrivals = [c["arrival"] for c in candidates if not c["reasons"]]
        urgent = bool(arrivals) and package.deadline - min(arrivals) <= CRITICAL_SLACK
        for candidate in candidates:
            candidate["urgent"] = urgent
            candidate["requires_dispatch"] = candidate["dispatch_time"] <= sim_time + 1e-9
            candidate["policy_reason"] = None
            if (candidate["requires_dispatch"] and not urgent
                    and candidate.get("needs_return_charging", False)
                    and candidate.get("charging_demand", 0) >= 2 * max(len(charging_pads), 1)
                    and candidate.get("return_pad_wait", 0.0) > MAX_RETURN_PAD_WAIT):
                candidate["policy_reason"] = "Fleet saturated: projected return charging congestion"
    return build_matrix(
        drones, packages, sim_time,
        lambda d, p, plan: candidate_details(
            d, p, sim_time, ALLOWED_STATES, plan, all_packages=packages,
            drones=drones, charging_pads=charging_pads, reserve_fraction=reserve_fraction,
        ),
        lambda d, p, c: calculate_predictive_assignment_features(d, p, c, sim_time),
        lambda f, distance, average, p: calculate_predictive_assignment_score(
            f, distance, average, sim_time, p.deadline,
        ),
        package_plans, prepare,
    )


def schedule_packages(drones, packages, sim_time, charging_pads,
                      reserve_fraction=None, min_reserve=None):
    algorithm = "v3"
    reserve_fraction = _reserve_fraction(reserve_fraction)
    min_reserve = MIN_RESERVE if min_reserve is None else min_reserve
    if not isinstance(min_reserve, int) or isinstance(min_reserve, bool) or min_reserve < 0:
        raise ValueError("min_reserve must be a nonnegative integer")
    validate_packages(drones, packages, sim_time)
    _execute_v3_charging(drones, packages, sim_time, charging_pads, reserve_fraction)
    matrix, pending_packages = build_cost_matrix(
        drones, packages, sim_time, charging_pads=charging_pads, reserve_fraction=reserve_fraction,
    )
    healthy = [d for d in drones.values() if d.status not in ("FAILED", "QUARANTINED")]
    effective_reserve = min(min_reserve, max(0, len(healthy) - 1))
    usable = [d for d in healthy if d.status in ("IDLE", "CHARGING", "WAITING_FOR_CHARGE")
              and d.current_package is None and d.payload == 0
              and math.hypot(d.x - BASE[0], d.y - BASE[1]) <= 1e-6
              and d.battery >= 0.20 * d.battery_capacity]
    dispatch_budget = (len(healthy) if effective_reserve == 0
                       else max(0, len(usable) - effective_reserve))
    best_assignment = find_max_coverage_assignment(
        matrix, pending_packages, dispatch_budget, cost_first=True,
    )
    assigned_pids = set()
    for drone in drones.values():
        drone.preparation_package = None
    selected_future = {p.id for p, _ in best_assignment or []}
    for package, candidate in best_assignment or []:
        drone = drones[candidate["drone_id"]]
        drone.target_battery = candidate["target_battery"]
        matrix[package.id]["plan"] = {
            "drone_id": drone.id, "package_id": package.id,
            "target_battery": candidate["target_battery"],
            "charge_end": candidate["dispatch_time"],
            "predicted_arrival": candidate["arrival"],
        }
        if candidate["dispatch_time"] <= sim_time + 1e-9:
            if drone.charging_pad is not None:
                charging_pads[drone.charging_pad] = None
                drone.charging_pad = None
            assign_package(drone, package, sim_time, algorithm, matrix[package.id]["plan"])
            assigned_pids.add(package.id)
        else:
            drone.preparation_package = package.id
            reason = (
                f"Predicted for Drone {drone.id}, waiting until "
                f"dispatch time {candidate['dispatch_time']:.1f}"
            )
            last = package.decision_history[-1] if package.decision_history else None
            same_forecast = (
                last is not None
                and last.get("action") == "DEFERRED"
                and last.get("selected_drone") == drone.id
                and last.get("predicted_dispatch_time") is not None
                and abs(last["predicted_dispatch_time"] - candidate["dispatch_time"]) < 1.0
            )
            if not same_forecast:
                package.decision_history.append({
                    "sim_time": sim_time, "algorithm": algorithm,
                    "action": "DEFERRED", "selected_drone": drone.id,
                    "reason": reason,
                    "predicted_dispatch_time": candidate["dispatch_time"],
                    "candidates": matrix[package.id]["all_candidates_log"],
                    "preparation": matrix[package.id]["plan"],
                })

    for package in pending_packages:
        if package.id not in assigned_pids and package.id not in selected_future:
            data = matrix[package.id]
            reason = (
                "Dynamic reserve or charging-aware global assignment; retry later"
                if data["candidates"] else next(
                    (c["policy_reason"] for c in data["all_candidates_log"] if c.get("policy_reason")),
                    "No drone available with sufficient time and return energy; retry later",
                )
            )
            log_deferred(package, sim_time, algorithm, data, reason)
    _execute_v3_charging(drones, packages, sim_time, charging_pads, reserve_fraction)
