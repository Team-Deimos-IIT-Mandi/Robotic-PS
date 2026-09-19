from ..assignment_costs.features import calculate_assignment_features
from ..assignment_costs.v2_cost import calculate_assignment_score_v2
from ..charging import manage_charging_infrastructure
from .common import build_matrix, candidate_details, dispatch_global_assignment, validate_packages
from .optimizer import find_max_coverage_assignment

ALLOWED_STATES = ("IDLE", "WAITING_FOR_CHARGE", "CHARGING")


def build_cost_matrix(drones, packages, sim_time, package_plans=None, charging_pads=None,
                      reserve_fraction=None):
    return build_matrix(
        drones, packages, sim_time,
        lambda d, p, plan: candidate_details(d, p, sim_time, ALLOWED_STATES, plan),
        lambda d, p, c: calculate_assignment_features(drones, d.id, p, sim_time),
        lambda f, distance, average, p: calculate_assignment_score_v2(f, distance, average),
        package_plans,
    )


def schedule_packages(drones, packages, sim_time, charging_pads):
    validate_packages(drones, packages, sim_time)
    preparation = manage_charging_infrastructure(drones, packages, charging_pads, sim_time)
    package_plans = {plan["package_id"]: plan for plan in preparation.values()}
    matrix, pending = build_cost_matrix(drones, packages, sim_time, package_plans, charging_pads)
    selected = find_max_coverage_assignment(matrix, pending)
    dispatch_global_assignment(drones, matrix, pending, sim_time, charging_pads, "v2", selected)
