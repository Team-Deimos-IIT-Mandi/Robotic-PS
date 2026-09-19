from .drone_sim import BASE

def assign_package(drone, package, sim_time, algorithm="v2", plan=None):
    package.status = "ASSIGNED"
    drone.status = "DELIVERY"
    drone.target = (package.x, package.y)
    drone.payload = package.weight
    drone.current_package = package.id
    package.assigned_drone = drone.id
    
    if not hasattr(package, 'decision_history'):
        package.decision_history = []
    package.decision_history.append({
        "sim_time": sim_time, 
        "algorithm": algorithm,
        "action": "ASSIGNED",
        "selected_drone": drone.id,
        "reason": "Optimal global assignment", 
        "preparation": plan,
    })

def abort_mission(drone, package, sim_time, reason):
    if not hasattr(package, 'decision_history'):
        package.decision_history = []
    package.decision_history.append({
        "sim_time": sim_time,
        "action": "ABORTED",
        "reason": reason
    })
    drone.status = "RETURNING"
    drone.target = (BASE[0], BASE[1])

def complete_delivery(drone, package, sim_time, dt, remaining_dt):
    package.delivered = True
    package.delivered_at = sim_time + dt - remaining_dt
    if package.delivered_at <= package.deadline + 1e-9:
        package.status = "DELIVERED_ON_TIME"
        package.outcome_reason = None
    else:
        package.status = "DELIVERED_LATE"
        package.outcome_reason = "Arrival after deadline"

    drone.payload = 0.0
    drone.status = "RETURNING"
    drone.target = (BASE[0], BASE[1])

def return_to_base(drone, packages, sim_time):
    if drone.current_package is not None:
        pkg = packages[drone.current_package]
        if not pkg.delivered:
            pkg.status = "PENDING"
            pkg.assigned_drone = None
            if not hasattr(pkg, 'decision_history'):
                pkg.decision_history = []
            pkg.decision_history.append({
                "sim_time": sim_time,
                "action": "RETURNED_TO_BASE",
                "reason": "Dropped aborted package at base"
            })
    
    drone.target = None
    drone.payload = 0.0
    drone.current_package = None

    if drone.battery < 0.20 * drone.battery_capacity:
        drone.status = "WAITING_FOR_CHARGE"
    else:
        drone.status = "IDLE"
