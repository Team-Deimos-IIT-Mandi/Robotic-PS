from .charging import manage_charging_infrastructure
from .assignment_algorithms import baseline, v1, v2, v3
from .assignment_algorithms.common import ideal_feasibility
from .assignment_algorithms.optimizer import find_max_coverage_assignment
from .assignment_algorithms.v3 import (
    calculate_predictive_assignment_features, calculate_predictive_assignment_score,
)
from .assignment_algorithms.v3_charging import (
    RESERVE_FRACTION, MIN_RESERVE, CRITICAL_SLACK, RETURN_WINDOW, MAX_RETURN_PAD_WAIT,
    WAITING_QUEUE_POLICY, _reserve_fraction as _validate_reserve_fraction,
    _package_charge_target, _future_charge_target, _project_state_at_base,
    _charge_duration, _candidate_pad_wait, _return_charging_forecast, _execute_v3_charging,
)

ALGORITHMS = {"baseline": baseline, "v1": v1, "v2": v2, "v3": v3}


def _algorithm_module(algorithm):
    try:
        return ALGORITHMS[algorithm]
    except KeyError:
        raise ValueError(f"Unknown assignment algorithm: {algorithm!r}") from None


def _reserve_fraction(value):
    return _validate_reserve_fraction(RESERVE_FRACTION if value is None else value)


def candidate_details(drone, package, sim_time, allowed, plan=None, algorithm="v3",
                      all_packages=None, drones=None, charging_pads=None,
                      reserve_fraction=None):
    module = _algorithm_module(algorithm)
    if algorithm == "v3":
        reserve_fraction = _reserve_fraction(reserve_fraction)
    return module.candidate_details(
        drone, package, sim_time, allowed, plan, algorithm, all_packages,
        drones, charging_pads, reserve_fraction,
    )


def build_cost_matrix(drones, packages, sim_time, algorithm, package_plans=None,
                      charging_pads=None, reserve_fraction=None):
    module = _algorithm_module(algorithm)
    if algorithm == "v3":
        reserve_fraction = _reserve_fraction(reserve_fraction)
    return module.build_cost_matrix(
        drones, packages, sim_time, package_plans, charging_pads, reserve_fraction,
    )


def schedule_packages(drones, packages, sim_time, charging_pads, algorithm,
                      reserve_fraction=None, min_reserve=None):
    module = _algorithm_module(algorithm)
    if algorithm == "v3":
        return module.schedule_packages(
            drones, packages, sim_time, charging_pads,
            reserve_fraction=_reserve_fraction(reserve_fraction),
            min_reserve=MIN_RESERVE if min_reserve is None else min_reserve,
        )
    return module.schedule_packages(drones, packages, sim_time, charging_pads)
