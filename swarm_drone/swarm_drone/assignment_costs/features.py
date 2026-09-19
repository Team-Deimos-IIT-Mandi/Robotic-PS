from ..physics import *

def calculate_assignment_features(drones, drone_id, package, sim_time):
    drone = drones[drone_id]
    
    # 1. Deadline slack fraction
    delivery_time = calculate_delivery_time(drone, package)
    remaining_deadline = package.deadline - sim_time
    slack = remaining_deadline - delivery_time
    slack_fraction = slack / max(remaining_deadline, 1e-6)
    deadline_cost = 1.0 - slack_fraction
    
    # 2. Energy fraction
    required_energy = calculate_required_battery(drone, package)
    energy_cost = required_energy / max(drone.battery, 1e-6)

    distance = calculate_mission_distance(drone, package)
    
    # 4. Charging risk
    remaining_fraction = (drone.battery - required_energy) / max(drone.battery_capacity, 1e-6)
    if remaining_fraction > 0.30:
        charging_risk = 0.0
    elif remaining_fraction > 0.15:
        charging_risk = 0.5
    else:
        charging_risk = 1.0
    
    return {
        "drone_id": drone.id,
        "deadline_cost": deadline_cost,
        "energy_cost": energy_cost,
        "raw_distance": distance,
        "raw_utilization": drone.total_flight_time,
        "charging_risk": charging_risk,
        "slack": slack
    }
