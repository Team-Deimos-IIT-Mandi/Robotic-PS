import math
from ..drone_sim import DroneState, BASE
from ..physics import calculate_delivery_time, calculate_required_battery
from ..fsm import assign_package


def ideal_feasibility(package, drones, sim_time=None):
    if not drones:
        return False, "No drones in fleet"
    if package.weight > 2.5:
        return False, "Payload exceeds fleet limit"

    ideal = DroneState(id=0, x=float(BASE[0]), y=float(BASE[1]))
    ideal_time = calculate_delivery_time(ideal, package)
    if sim_time is None:
        sim_time = package.request_time
    if sim_time + ideal_time > package.deadline + 1e-9:
        return False, "Even immediate departure cannot meet deadline"

    required_battery = calculate_required_battery(ideal, package)
    max_capacity = max(d.battery_capacity for d in drones.values())
    if required_battery > max_capacity:
        return False, "Round trip exceeds every drone's full usable capacity"

    return True, None


def validate_packages(drones, packages, sim_time):
    for package in packages.values():
        if package.status != "PENDING" or package.assigned_drone is not None or package.delivered:
            continue
        if package.request_time > sim_time:
            continue

        values = (package.x, package.y, package.weight, package.deadline, package.request_time)
        if not all(math.isfinite(v) for v in values) or package.weight < 0:
            package.status = "REJECTED"
            package.outcome_reason = "Invalid request"
            package.assigned_drone = -1
            continue

        if sim_time > package.deadline:
            package.status = "EXPIRED"
            package.outcome_reason = "Deadline passed while waiting"
            package.assigned_drone = -1
            continue

        feasible, reason = ideal_feasibility(package, drones, sim_time)
        if not feasible:
            package.status = "REJECTED"
            package.outcome_reason = reason
            package.assigned_drone = -1
            package.decision_history.append({
                "sim_time": sim_time, "action": package.status,
                "reason": reason, "candidates": []
            })
            continue


def candidate_details(drone, package, sim_time, allowed, plan=None, algorithm=None,
                      all_packages=None, drones=None, charging_pads=None,
                      reserve_fraction=None):
    reasons = []
    if drone.status not in allowed:
        reasons.append("Drone unavailable: " + drone.status)
    if package.weight > 2.5:
        reasons.append("Payload exceeds capacity")
    arrival = sim_time + calculate_delivery_time(drone, package)
    energy = calculate_required_battery(drone, package)
    if arrival > package.deadline + 1e-9:
        reasons.append("Arrival after deadline")
    if energy > drone.battery:
        reasons.append("Insufficient battery for delivery and return")
    return {
        "drone_id": drone.id, "status": drone.status, "battery": drone.battery,
        "capacity": drone.battery_capacity, "arrival": arrival,
        "required_energy": energy, "reasons": reasons,
        "slack": package.deadline - arrival,
    }


def build_matrix(drones, packages, sim_time, candidate_fn, feature_fn, score_fn,
                 package_plans=None, prepare_candidates=None):
    package_plans = package_plans or {}
    pending = [
        p for p in packages.values()
        if p.status == "PENDING" and p.assigned_drone is None and not p.delivered
        and p.request_time <= sim_time
    ]
    matrix = {}
    all_features = []
    for package in pending:
        plan = package_plans.get(package.id)
        candidates = [candidate_fn(d, package, plan) for d in drones.values()]
        if prepare_candidates is not None:
            prepare_candidates(candidates, package)
        feasible = [c for c in candidates if not c["reasons"] and not c.get("policy_reason")]
        matrix[package.id] = {
            "package": package, "candidates": feasible,
            "all_candidates_log": candidates, "plan": plan,
        }
        for candidate in feasible:
            drone = drones[candidate["drone_id"]]
            features = feature_fn(drone, package, candidate)
            candidate["features"] = features
            all_features.append(features)
    average_time = sum(d.total_flight_time for d in drones.values()) / len(drones) if drones else 0
    max_distance = max((f["raw_distance"] for f in all_features), default=0)
    for data in matrix.values():
        for candidate in data["candidates"]:
            components = score_fn(candidate["features"], max_distance, average_time, data["package"])
            candidate["score_components"] = components
            candidate["cost"] = components["score"]
    return matrix, pending


def dispatch(drone, package, sim_time, charging_pads, algorithm, plan):
    if drone.charging_pad is not None:
        charging_pads[drone.charging_pad] = None
        drone.charging_pad = None
    assign_package(drone, package, sim_time, algorithm, plan)


def log_deferred(package, sim_time, algorithm, data, reason):
    package.decision_history.append({
        "sim_time": sim_time, "algorithm": algorithm,
        "action": "DEFERRED", "selected_drone": None,
        "reason": reason, "candidates": data["all_candidates_log"],
        "preparation": data["plan"],
    })


def dispatch_global_assignment(drones, matrix, pending, sim_time, charging_pads,
                               algorithm, best_assignment):
    selected = set()
    for package, candidate in best_assignment or []:
        dispatch(drones[candidate["drone_id"]], package, sim_time, charging_pads,
                 algorithm, matrix[package.id]["plan"])
        selected.add(package.id)
    for package in pending:
        if package.id not in selected:
            data = matrix[package.id]
            reason = ("Not selected in max-coverage global assignment" if data["candidates"]
                      else "No drone available with sufficient time and return energy; retry later")
            log_deferred(package, sim_time, algorithm, data, reason)
