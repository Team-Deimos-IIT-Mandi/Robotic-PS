import math
import random
from .drone_sim import BASE

def generate_wind_events(seed, max_time=40*60):
    """
    Generates a list of deterministic wind burst events for a simulation run.
    """
    rng = random.Random(seed)
    events = []
    
    t = 0.0
    while t < max_time:
        # Time until next wind event
        t += rng.uniform(30.0, 100.0)
        if t >= max_time:
            break
            
        duration = rng.uniform(10.0, 30.0)
        
        # Center of the wind burst (within a reasonable distance from the base)
        center_x = BASE[0] + rng.uniform(-800, 800)
        center_y = BASE[1] + rng.uniform(-800, 800)
        
        # Spatial size of the burst
        radius = rng.uniform(150.0, 300.0)
        angle = rng.uniform(0, 2 * math.pi)
        speed = rng.uniform(1.0, 5.0)
        
        vx = speed * math.cos(angle)
        vy = speed * math.sin(angle)
        
        events.append({
            'start': t,
            'end': t + duration,
            'x': center_x,
            'y': center_y,
            'r': radius,
            'vx': vx,
            'vy': vy
        })
        
    return events

def get_wind(x, y, sim_time, events):
    """
    Returns the accumulated wind vector at (x, y) at sim_time, factoring in 
    distance-scaled smoothing from the active events.
    """
    if sim_time < 0.0:
        return 0.0, 0.0
        
    total_vx = 0.0
    total_vy = 0.0
    
    for e in events:
        if e['start'] <= sim_time <= e['end']:
            dist = math.hypot(x - e['x'], y - e['y'])
            if dist <= e['r']:
                # Wind strength tapers off from 1.0 at the center to 0.0 at the edge
                strength = max(0.0, 1.0 - (dist / e['r']))
                total_vx += e['vx'] * strength
                total_vy += e['vy'] * strength
                
    return total_vx, total_vy
