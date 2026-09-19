from ..assignment_costs.baseline_cost import calculate_baseline_score
from ..assignment_costs.features import calculate_assignment_features
from ..assignment_costs.v1_cost import calculate_assignment_score
from .common import build_matrix, candidate_details, dispatch, log_deferred, validate_packages

ALLOWED_STATES = ("IDLE",)


def build_cost_matrix(drones, packages, sim_time, package_plans=None, charging_pads=None,
                      reserve_fraction=None):
    return build_matrix(
        drones, packages, sim_time,
        lambda d, p, plan: candidate_details(d, p, sim_time, ALLOWED_STATES, plan),
        lambda d, p, c: calculate_assignment_features(drones, d.id, p, sim_time),
        lambda f, distance, average, p: calculate_assignment_score(f, distance, average),
        package_plans,
    )


def schedule_packages(drones, packages, sim_time, charging_pads):
    validate_packages(drones, packages, sim_time)
    matrix, pending = build_cost_matrix(drones, packages, sim_time, charging_pads=charging_pads)
    for package in pending:
        data = matrix[package.id]
        selected, reason = calculate_baseline_score(data["candidates"])
        if selected:
            dispatch(drones[selected["drone_id"]], package, sim_time, charging_pads,
                     "baseline", data["plan"])
        else:
            log_deferred(package, sim_time, "baseline", data, reason)
