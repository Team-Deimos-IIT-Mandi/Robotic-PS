import math
from .drone_sim import BASE

def move_towards(drone, target, speed, dt, sim_time, wind_events):
    target_x, target_y = target

    dx = target_x - drone.x
    dy = target_y - drone.y

    distance = math.sqrt(dx * dx + dy * dy)

    if distance == 0:
        return 0.0, 0.0, True

    # 1. Base drone movement (nose pointing at target)
    direction_x = dx / distance
    direction_y = dy / distance
    
    movement_x = direction_x * speed
    movement_y = direction_y * speed
    
    # 2. Get wind and convert to pixels/s
    from .wind import get_wind
    wind_x_m, wind_y_m = get_wind(drone.x, drone.y, sim_time, wind_events)
    wind_x_px = meters_to_pixels(wind_x_m)
    wind_y_px = meters_to_pixels(wind_y_m)
    
    # 3. Apply wind drift
    actual_vx = movement_x + wind_x_px
    actual_vy = movement_y + wind_y_px
    
    actual_movement_x = actual_vx * dt
    actual_movement_y = actual_vy * dt
    
    actual_distance = math.sqrt(actual_movement_x**2 + actual_movement_y**2)
    
    # 4. Check if we reached target
    # Project movement onto the vector to the target to see if we passed it
    progress = (actual_movement_x * dx + actual_movement_y * dy) / distance
    
    if progress >= distance:
        # Reached target
        fraction = distance / max(progress, 1e-9)
        actual_time = dt * fraction
        
        drone.x = target_x
        drone.y = target_y
        
        return distance, actual_time, True

    # Drone does not reach target
    drone.x += actual_movement_x
    drone.y += actual_movement_y

    return actual_distance, dt, False

def calculate_battery_consumption(time, payload):
    FULL_PAYLOAD = 2.5
    FULL_PAYLOAD_ENDURANCE = 25 * 60
    full_payload_rate = 100.0 / FULL_PAYLOAD_ENDURANCE
    empty_payload_rate = 0.7 * full_payload_rate
    payload_ratio = payload / FULL_PAYLOAD
    consumption_rate = empty_payload_rate + payload_ratio * (full_payload_rate - empty_payload_rate)
    return time * consumption_rate

def pixels_to_meters(distance_pixels):
    PIXELS_PER_METER = 10.0
    return distance_pixels / PIXELS_PER_METER

def meters_to_pixels(distance_meters):
    PIXELS_PER_METER = 10.0
    return distance_meters * PIXELS_PER_METER

def calculate_speed(payload):
    max_speed = 12.0
    max_payload = 2.5
    if payload <= 0:
        return max_speed
    if payload >= max_payload:
        return max_speed * 0.7
    speed_factor = 1.0 - 0.3 * (payload / max_payload)
    return max_speed * speed_factor

def calculate_delivery_time(drone, package):
    # The deadline applies at drop-off; return energy is checked separately.
    distance_pixels = math.hypot(package.x - drone.x, package.y - drone.y)
    return pixels_to_meters(distance_pixels) / calculate_speed(package.weight)

def calculate_mission_time(drone, package):
    to_package_pixels = math.sqrt((package.x - drone.x)**2 + (package.y - drone.y)**2)
    to_base_pixels = math.sqrt((BASE[0] - package.x)**2 + (BASE[1] - package.y)**2)
    
    to_package_meters = pixels_to_meters(to_package_pixels)
    to_base_meters = pixels_to_meters(to_base_pixels)
    
    delivery_speed = calculate_speed(package.weight)
    return_speed = calculate_speed(0.0)
    
    time_to_package = to_package_meters / delivery_speed
    time_to_base = to_base_meters / return_speed
    
    return time_to_package + time_to_base

def calculate_mission_distance(drone, package):
    to_package = math.sqrt((package.x - drone.x)**2 + (package.y - drone.y)**2)
    to_base = math.sqrt((BASE[0] - package.x)**2 + (BASE[1] - package.y)**2)
    return pixels_to_meters(to_package) + pixels_to_meters(to_base)

def calculate_required_battery(drone, package):
    to_package_pixels = math.sqrt((package.x - drone.x)**2 + (package.y - drone.y)**2)
    to_base_pixels = math.sqrt((BASE[0] - package.x)**2 + (BASE[1] - package.y)**2)
    
    to_package_meters = pixels_to_meters(to_package_pixels)
    to_base_meters = pixels_to_meters(to_base_pixels)
    
    delivery_speed = calculate_speed(package.weight)
    return_speed = calculate_speed(0.0)
    
    time_to_package = to_package_meters / delivery_speed
    time_to_base = to_base_meters / return_speed
    
    delivery_battery = calculate_battery_consumption(time_to_package, package.weight)
    return_battery = calculate_battery_consumption(time_to_base, 0.0)
    
    return delivery_battery + return_battery

def is_mission_feasible(drone, package, sim_time):
    if package.weight > 2.5:
        return False
    remaining_deadline = package.deadline - sim_time
    delivery_time = calculate_delivery_time(drone, package)
    if delivery_time > remaining_deadline:
        return False
    required_battery = calculate_required_battery(drone, package)
    reserve_energy = drone.battery - required_battery
    if reserve_energy < 0.11 * drone.battery_capacity:
        return False
    return True
