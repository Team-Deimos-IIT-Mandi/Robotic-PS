import math
from .drone_sim import BASE, DroneState
from .physics import *

FULL_CHARGE_TIME = 40 * 60

def apply_battery_degradation(drone):
    drone.cycle_count += 1
    drone.battery_capacity *= 0.9995

    # Battery can never exceed the new degraded capacity
    drone.battery = min(drone.battery, drone.battery_capacity)

def calculate_charge_time(drone):
    missing_fraction = (
        drone.battery_capacity - drone.battery
    ) / drone.battery_capacity
    return FULL_CHARGE_TIME * missing_fraction

def get_free_charging_pad(charging_pads):
    for pad_id, drone_id in charging_pads.items():
        if drone_id is None:
            return pad_id
    return None

def start_charging(drone, charging_pads):
    pad_id = get_free_charging_pad(charging_pads)
    if pad_id is None:
        return False
    charging_pads[pad_id] = drone.id
    drone.charging_pad = pad_id
    drone.status = "CHARGING"
    return True

def update_charging(drone, dt, charging_pads):
    drone.target_battery = min(drone.target_battery, drone.battery_capacity)
    charge_rate = drone.battery_capacity / FULL_CHARGE_TIME
    charged_amount = charge_rate * dt
    drone.battery = min(drone.battery + charged_amount, drone.battery_capacity)
    
    if drone.battery >= drone.target_battery:
        drone.battery = drone.target_battery
        pad_id = drone.charging_pad
        if pad_id is not None:
            charging_pads[pad_id] = None
        drone.charging_pad = None
        drone.status = "IDLE"

def consume_battery(drone, dt):
    battery_used = calculate_battery_consumption(
        dt,
        drone.payload
    )

    drone.battery -= battery_used
    drone.battery = max(0.0, drone.battery)

    drone.cycle_energy += battery_used

    while drone.cycle_energy >= 100.0:
        drone.cycle_energy -= 100.0
        apply_battery_degradation(drone)

def manage_charging_infrastructure(drones, packages, charging_pads, sim_time):
    plans = plan_fleet_preparation(drones, packages, charging_pads, sim_time)
    eligible = charging_candidates_at_base(drones)
    # Preserve pads held by drones outside this planner's scope.
    new_pads = {
        pad: (owner if owner is not None and owner not in eligible else None)
        for pad, owner in charging_pads.items()
    }
    for drone in eligible.values():
        drone.target_battery = (plans[drone.id]["target_battery"] if drone.id in plans
                                else drone.battery_capacity)
    # Execute only the current head of each pad's predicted queue.
    for drone_id, plan in plans.items():
        if plan["pad_id"] is not None and plan["charge_start"] <= sim_time + 1e-9:
            new_pads[plan["pad_id"]] = drone_id
    # Fill otherwise unused pads, without charging a ready planned drone further.
    opportunistic = sorted(
        (d for d in eligible.values() if d.id not in plans and d.battery < d.battery_capacity),
        key=lambda d: (d.charging_pad is None, d.battery / d.battery_capacity, d.id),
    )
    for drone in opportunistic:
        free = [pad for pad, owner in new_pads.items() if owner is None]
        if not free:
            break
        pad = drone.charging_pad if drone.charging_pad in free else free[0]
        new_pads[pad] = drone.id

    # Commit together so a pad move cannot clear another drone's new allocation.
    allocated = {owner: pad for pad, owner in new_pads.items() if owner is not None}
    charging_pads.update(new_pads)
    for drone in eligible.values():
        drone.charging_pad = allocated.get(drone.id)
        if drone.charging_pad is not None:
            drone.status = "CHARGING"
        elif drone.id in plans and drone.battery + 1e-9 < drone.target_battery:
            drone.status = "WAITING_FOR_CHARGE"
        else:
            drone.status = "IDLE"
    return plans

def charging_candidates_at_base(drones):
    """Only empty, available drones physically at the pickup base can prepare."""
    return {
        d.id: d for d in drones.values()
        if d.status in ("IDLE", "WAITING_FOR_CHARGE", "CHARGING")
        and d.current_package is None and d.payload == 0
        and all(math.isfinite(v) for v in (d.x, d.y, d.battery, d.battery_capacity))
        and d.battery_capacity > 0 and 0 <= d.battery <= d.battery_capacity
        and math.hypot(d.x - BASE[0], d.y - BASE[1]) <= 1e-6
    }

def plan_fleet_preparation(drones, packages, charging_pads, sim_time):
    """Temporary one-job-per-drone matching with a shared charging calendar.

    Process earlier deadlines first. Choose the earliest achievable arrival,
    breaking ties by charging energy, accumulated flight time, then drone ID.
    Existing opportunistic charging can be preempted immediately in this model.
    Plans are recomputed each tick; they never assign physical package ownership.
    """
    available = charging_candidates_at_base(drones)
    # A pad held by an unavailable drone cannot be promised to a preparation.
    pad_ready = {
        pad: (sim_time if owner is None or owner in available else float("inf"))
        for pad, owner in charging_pads.items()
    }
    pending = sorted(
        (p for p in packages.values()
         if p.status == "PENDING" and p.assigned_drone is None and not p.delivered
         and all(math.isfinite(v) for v in (p.x, p.y, p.weight, p.request_time, p.deadline))
         and 0 <= p.weight <= 2.5 and p.request_time <= sim_time <= p.deadline),
        key=lambda p: (p.deadline, p.request_time, p.id),
    )
    plans = {}
    for package in pending:
        choices = []
        for drone in available.values():
            required = calculate_required_battery(drone, package)
            if required > drone.battery_capacity:
                continue
            # Preserve the existing reserve policy but add 1% buffer to avoid floating point aborts
            target = min(required + 0.11 * drone.battery_capacity, drone.battery_capacity)
            added_energy = max(0.0, target - drone.battery)
            charge_seconds = added_energy / drone.battery_capacity * FULL_CHARGE_TIME
            pad = None
            start = sim_time
            if charge_seconds > 1e-9:
                if not pad_ready:
                    continue
                pad = min(pad_ready, key=lambda key: (
                    pad_ready[key], key != drone.charging_pad, key))
                start = pad_ready[pad]
            ready = start + charge_seconds
            arrival = ready + calculate_delivery_time(drone, package)
            if arrival > package.deadline + 1e-9:
                continue
            choices.append({
                "drone_id": drone.id, "package_id": package.id,
                "required_energy": required, "target_battery": target,
                "added_energy": added_energy, "pad_id": pad,
                "charge_start": start, "charge_end": ready,
                "predicted_arrival": arrival, "slack": package.deadline - arrival,
            })
        if not choices:
            continue
        selected = min(choices, key=lambda c: (
            c["predicted_arrival"], c["added_energy"],
            available[c["drone_id"]].total_flight_time, c["drone_id"]))
        drone_id = selected["drone_id"]
        # Copies keep candidate logs finite and independent of later state updates.
        selected["alternatives"] = [dict(c) for c in choices]
        plans[drone_id] = selected
        del available[drone_id]
        if selected["pad_id"] is not None:
            pad_ready[selected["pad_id"]] = selected["charge_end"]
    return plans
