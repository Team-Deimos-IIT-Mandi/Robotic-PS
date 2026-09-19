import math
from ..drone_sim import DroneState, BASE
from ..physics import (
    calculate_required_battery, calculate_mission_time, calculate_speed,
    calculate_battery_consumption, pixels_to_meters,
)
from ..charging import FULL_CHARGE_TIME

RESERVE_FRACTION = 0.11
MIN_RESERVE = 2
CRITICAL_SLACK = 15.0
RETURN_WINDOW = 30.0
MAX_RETURN_PAD_WAIT = 60.0
WAITING_QUEUE_POLICY = "FIFO by wait_start_time, then drone id"


def _reserve_fraction(value):
    value = RESERVE_FRACTION if value is None else value
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("reserve_fraction must be finite and between 0 and 1")
    return value


def _package_charge_target(drone, package, reserve_fraction):
    ideal = DroneState(id=0, x=float(BASE[0]), y=float(BASE[1]))
    required = calculate_required_battery(ideal, package)
    return min(drone.battery_capacity, required + reserve_fraction * drone.battery_capacity)


def _future_charge_target(drone, battery_at_base, packages, sim_time, reserve_fraction):
    """Use a soft package plan, or full recovery charging below the return threshold."""
    package = (packages or {}).get(drone.preparation_package)
    if (package is not None and package.status == "PENDING"
            and package.assigned_drone is None and not package.delivered
            and package.request_time <= sim_time <= package.deadline):
        return _package_charge_target(drone, package, reserve_fraction)
    if battery_at_base < 0.20 * drone.battery_capacity:
        return drone.battery_capacity
    return battery_at_base


def _project_state_at_base(drone, all_packages, reasons):
    """Return the future time and battery when a drone next reaches base."""
    time_to_base = 0.0
    battery_at_base = drone.battery

    if drone.status == "DELIVERY":
        current_package = None if all_packages is None else all_packages.get(drone.current_package)
        if current_package is None:
            reasons.append("Missing current package info for DELIVERY drone")
        else:
            time_to_base = calculate_mission_time(drone, current_package)
            battery_at_base -= calculate_required_battery(drone, current_package)
    elif drone.status == "RETURNING":
        dist_to_base = math.hypot(BASE[0] - drone.x, BASE[1] - drone.y)
        time_to_base = pixels_to_meters(dist_to_base) / calculate_speed(drone.payload)
        battery_at_base -= calculate_battery_consumption(time_to_base, drone.payload)
    elif drone.status not in ("IDLE", "CHARGING", "WAITING_FOR_CHARGE", "FAILED", "QUARANTINED"):
        reasons.append(f"Unhandled drone status: {drone.status}")

    return time_to_base, battery_at_base


def _charge_duration(capacity, battery, target_battery):
    """Charge duration in seconds, using the simulator's linear charge model."""
    missing = max(0.0, target_battery - max(0.0, battery))
    return missing / max(capacity / FULL_CHARGE_TIME, 1e-9)


def _candidate_pad_wait(candidate, time_to_base, battery_at_base, target_battery,
                        drones, charging_pads, all_packages=None, sim_time=0.0,
                        reserve_fraction=None):
    """Forecast FIFO charging demand, including projected airborne arrivals."""
    reserve_fraction = _reserve_fraction(reserve_fraction)
    if battery_at_base >= target_battery - 1e-9:
        return 0.0
    if candidate.status == "CHARGING":
        return 0.0
    if not charging_pads:
        return float("inf")

    pad_free = {
        pad_id: (0.0 if owner is None else float("inf"))
        for pad_id, owner in charging_pads.items()
    }
    for drone in drones.values():
        if drone.id == candidate.id or drone.status != "CHARGING":
            continue
        if drone.charging_pad in pad_free:
            pad_free[drone.charging_pad] = _charge_duration(
                drone.battery_capacity, drone.battery,
                min(drone.target_battery, drone.battery_capacity),
            )

    waiting = []
    for drone in drones.values():
        if drone.id == candidate.id:
            continue
        if drone.status == "WAITING_FOR_CHARGE":
            joined = drone.wait_start_time if drone.wait_start_time is not None else sim_time
            waiting.append((joined, drone.id, drone, 0.0, drone.battery,
                            min(drone.target_battery, drone.battery_capacity)))
        elif drone.status in ("DELIVERY", "RETURNING"):
            reasons = []
            arrival, battery = _project_state_at_base(drone, all_packages, reasons)
            if reasons or battery < 0:
                continue
            target = _future_charge_target(
                drone, battery, all_packages, sim_time, reserve_fraction,
            )
            waiting.append((sim_time + arrival, drone.id, drone, arrival, battery, target))
    joined = (candidate.wait_start_time
              if candidate.status == "WAITING_FOR_CHARGE" and candidate.wait_start_time is not None
              else sim_time + time_to_base)
    waiting.append((joined, candidate.id, candidate, time_to_base, battery_at_base, target_battery))
    waiting.sort(key=lambda entry: (entry[0], entry[1]))

    candidate_wait = 0.0
    for _, _, drone, arrival_at_base, battery, desired_target in waiting:
        charge_time = _charge_duration(drone.battery_capacity, battery, desired_target)
        if charge_time <= 1e-9:
            continue
        pad_id = min(pad_free, key=lambda pad: (pad_free[pad], pad))
        charge_start = max(arrival_at_base, pad_free[pad_id])
        if drone.id == candidate.id:
            candidate_wait = charge_start - arrival_at_base
        pad_free[pad_id] = charge_start + charge_time

    return candidate_wait


def _return_charging_forecast(drone, package, dispatch_time, launch_battery,
                              drones, packages, charging_pads, sim_time, reserve_fraction):
    ideal = DroneState(id=drone.id, x=float(BASE[0]), y=float(BASE[1]),
                       status="RETURNING", battery_capacity=drone.battery_capacity)
    mission_time = calculate_mission_time(ideal, package)
    return_time = dispatch_time + mission_time
    return_battery = launch_battery - calculate_required_battery(ideal, package)
    needs_charge = return_battery < 0.20 * drone.battery_capacity
    demand = 0
    collisions = 0
    for other in drones.values():
        if other.id == drone.id:
            continue
        if other.status in ("CHARGING", "WAITING_FOR_CHARGE"):
            demand += 1
        elif other.status in ("DELIVERY", "RETURNING"):
            reasons = []
            arrival, battery = _project_state_at_base(other, packages, reasons)
            if reasons or battery < 0:
                continue
            target = _future_charge_target(other, battery, packages, sim_time, reserve_fraction)
            if battery >= target - 1e-9:
                continue
            if sim_time + arrival <= return_time + RETURN_WINDOW:
                demand += 1
            if abs(sim_time + arrival - return_time) <= RETURN_WINDOW:
                collisions += 1
    wait = 0.0
    if needs_charge:
        wait = _candidate_pad_wait(
            ideal, return_time - sim_time, return_battery, drone.battery_capacity,
            drones, charging_pads, packages, sim_time, reserve_fraction,
        )
    pad_count = max(len(charging_pads), 1)
    congestion_cost = demand / pad_count if needs_charge else 0.0
    return_cost = collisions / pad_count if needs_charge else 0.0
    if math.isfinite(wait):
        congestion_cost += wait / FULL_CHARGE_TIME
    elif needs_charge:
        congestion_cost += 1.0
    return {
        "predicted_return_time": return_time,
        "predicted_return_battery": return_battery,
        "needs_return_charging": needs_charge,
        "return_pad_wait": wait,
        "charging_demand": demand,
        "return_collisions": collisions,
        "congestion_cost": congestion_cost,
        "return_collision_cost": return_cost,
    }


def _execute_v3_charging(drones, packages, sim_time, charging_pads, reserve_fraction):
    """Execute live targets and FIFO starts without a separate fleet planner."""
    waiting = []
    for drone in drones.values():
        if (drone.status not in ("IDLE", "WAITING_FOR_CHARGE", "CHARGING")
                or drone.current_package is not None or drone.payload != 0
                or math.hypot(drone.x - BASE[0], drone.y - BASE[1]) > 1e-6):
            continue
        package = packages.get(drone.preparation_package)
        has_plan = (package is not None and package.status == "PENDING"
                    and package.assigned_drone is None and not package.delivered
                    and package.request_time <= sim_time <= package.deadline)
        if has_plan:
            drone.target_battery = _package_charge_target(drone, package, reserve_fraction)
        else:
            drone.preparation_package = None
            if drone.status == "WAITING_FOR_CHARGE" and drone.wait_start_time is None:
                drone.target_battery = drone.battery_capacity
        drone.target_battery = min(drone.target_battery, drone.battery_capacity)
        if drone.battery >= drone.target_battery - 1e-9:
            if drone.charging_pad is not None:
                charging_pads[drone.charging_pad] = None
                drone.charging_pad = None
            drone.status = "IDLE"
            drone.wait_start_time = None
        elif drone.status != "IDLE" or has_plan:
            if drone.status != "CHARGING":
                drone.status = "WAITING_FOR_CHARGE"
                if drone.wait_start_time is None:
                    drone.wait_start_time = sim_time
                waiting.append(drone)
    waiting.sort(key=lambda drone: (drone.wait_start_time, drone.id))
    for drone in waiting:
        free = [pad for pad, owner in charging_pads.items() if owner is None]
        if not free:
            break
        pad = min(free)
        charging_pads[pad] = drone.id
        drone.charging_pad = pad
        drone.status = "CHARGING"
        drone.wait_start_time = None
