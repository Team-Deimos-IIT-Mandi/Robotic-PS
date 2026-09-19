import math
from .drone_sim import BASE
from .wind import get_wind
from .physics import calculate_speed, calculate_battery_consumption, pixels_to_meters

def evaluate_mission_state(drone, package, sim_time, wind_events):
    # 1. Get current wind
    wx_m, wy_m = get_wind(drone.x, drone.y, sim_time, wind_events)
    
    # 2. Outbound Leg (Drone -> Package)
    dx_out = package.x - drone.x
    dy_out = package.y - drone.y
    dist_out_px = math.hypot(dx_out, dy_out)
    dist_out_m = pixels_to_meters(dist_out_px)
    
    delivery_feasible = True
    delivery_time = 0.0
    delivery_energy = 0.0
    
    if dist_out_m > 0:
        dir_out_x = dx_out / max(dist_out_px, 1e-9)
        dir_out_y = dy_out / max(dist_out_px, 1e-9)
        
        speed_out_m = calculate_speed(package.weight)
        
        # Wind projection on outbound vector
        w_proj_out = wx_m * dir_out_x + wy_m * dir_out_y
        veff_out = speed_out_m + w_proj_out
        
        if veff_out <= 0:
            delivery_feasible = False
        else:
            delivery_time = dist_out_m / veff_out
            delivery_energy = calculate_battery_consumption(delivery_time, package.weight)
            
    # 3. Return Leg (Package -> Base)
    dx_ret = BASE[0] - package.x
    dy_ret = BASE[1] - package.y
    dist_ret_px = math.hypot(dx_ret, dy_ret)
    dist_ret_m = pixels_to_meters(dist_ret_px)
    
    return_feasible = True
    return_time = 0.0
    return_energy = 0.0
    
    if dist_ret_m > 0:
        dir_ret_x = dx_ret / max(dist_ret_px, 1e-9)
        dir_ret_y = dy_ret / max(dist_ret_px, 1e-9)
        
        speed_ret_m = calculate_speed(0.0) # Empty payload on return
        
        w_proj_ret = wx_m * dir_ret_x + wy_m * dir_ret_y
        veff_ret = speed_ret_m + w_proj_ret
        
        if veff_ret <= 0:
            return_feasible = False
        else:
            return_time = dist_ret_m / veff_ret
            return_energy = calculate_battery_consumption(return_time, 0.0)
            
    # 4. Predict total arrival and check deadlines
    predicted_arrival = sim_time + delivery_time
    if predicted_arrival > package.deadline + 1e-9:
        delivery_feasible = False
        
    required_energy = delivery_energy + return_energy
    
    # 5. Evaluate battery margin
    reserve_energy = drone.battery - required_energy
    margin_fraction = reserve_energy / max(drone.battery_capacity, 1e-9)
    
    status = "SAFE"
    reason = "Mission on track"
    
    if not delivery_feasible:
        status = "ABORT"
        reason = "Delivery infeasible (deadline or wind)"
    elif not return_feasible:
        status = "ABORT"
        reason = "Return infeasible (headwind too strong)"
    elif margin_fraction < 0.10:
        status = "ABORT"
        reason = f"Battery margin dangerously low ({margin_fraction*100:.1f}%)"
    elif margin_fraction <= 0.20:
        status = "CAUTION"
        reason = f"Battery margin getting tight ({margin_fraction*100:.1f}%)"
        
    return {
        "sim_time": sim_time,
        "drone_id": drone.id,
        "battery": drone.battery,
        "wind": [wx_m, wy_m],
        "predicted_arrival": predicted_arrival,
        "deadline": package.deadline,
        "delivery_energy": delivery_energy,
        "return_energy": return_energy,
        "reserve": reserve_energy,
        "margin": margin_fraction,
        "status": status,
        "reason": reason
    }
