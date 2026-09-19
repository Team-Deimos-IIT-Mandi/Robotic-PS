import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone import simulation
from swarm_drone import drone_sim
def test_movement():
    print("Running test_movement...")
    drone = drone_sim.DroneState(id=1, x=0.0, y=0.0)
    target = (10.0, 0.0)
    # speed = 12 m/s, dt = 1/12 s, pixels per meter = 10
    # distance = 10 pixels = 1 meter
    # speed in pixels = 120 pixels/s
    speed_pixels = 120.0
    dt = 1/12
    
    distance_moved, actual_time, reached = simulation.move_towards(drone, target, speed_pixels, dt, -1.0, [])
    assert reached == True, "Drone should have reached the target"
    assert abs(drone.x - 10.0) < 1e-6, "Drone x position incorrect"
    assert abs(drone.y - 0.0) < 1e-6, "Drone y position incorrect"
    assert abs(distance_moved - 10.0) < 1e-6, "Distance moved incorrect"
    assert abs(actual_time - (10.0 / 120.0)) < 1e-6, "Actual time used incorrect"
    print("test_movement passed.")

def test_timestep():
    print("Running test_timestep...")
    drone = drone_sim.DroneState(id=1, x=0.0, y=0.0, status="DELIVERY", payload=0.0)
    drone.target = (24.0, 0.0) # 24 pixels = 2.4 meters. speed = 12 m/s = 120 px/s
    # actual time to reach = 24 / 120 = 0.2 s
    dt = 1.0
    packages = {1: drone_sim.PackageState(id=1, x=24.0, y=0.0, weight=0.0, request_time=0, deadline=100)}
    drone.current_package = 1
    charging_pads = {1: None, 2: None, 3: None}
    
    simulation.update_drone(drone, packages, dt, charging_pads, 0.0)
    
    # 0.2s spent delivering. 0.8s spent returning towards base (410, 350)
    assert drone.status == "RETURNING" or drone.status == "IDLE", f"Unexpected status {drone.status}"
    print("test_timestep passed.")

def test_battery():
    print("Running test_battery...")
    drone = drone_sim.DroneState(id=1, x=0.0, y=0.0, payload=0.0, battery=100.0)
    initial_battery = drone.battery
    dt = 10.0
    
    simulation.consume_battery(drone, dt)
    battery_used = simulation.calculate_battery_consumption(dt, drone.payload)
    final_battery = drone.battery
    
    assert abs(initial_battery - battery_used - final_battery) < 1e-6, "Battery conservation violated"
    print("test_battery passed.")

def test_payload():
    print("Running test_payload...")
    speed_empty = simulation.calculate_speed(0.0)
    speed_full = simulation.calculate_speed(2.5)
    assert speed_empty == 12.0, f"Expected 12.0, got {speed_empty}"
    assert abs(speed_full - 8.4) < 1e-6, f"Expected 8.4, got {speed_full}"
    assert simulation.calculate_speed(1.0) > simulation.calculate_speed(2.0), "Heavier payload should be slower"
    assert simulation.calculate_speed(2.5) < simulation.calculate_speed(0.0), "Full payload should be slower than empty"
    print("test_payload passed.")

def test_deadlines():
    print("Running test_deadlines...")
    base_x, base_y = simulation.BASE
    drone = drone_sim.DroneState(id=1, x=base_x, y=base_y)
    
    # We want distance = 120 meters = 1200 pixels from base.
    package = drone_sim.PackageState(
        id=1, x=base_x + 1200.0, y=base_y, 
        weight=0.0, request_time=0.0, deadline=30.0
    )
    
    sim_time = 0.0
    # Case A: Feasible (mission 20, remaining 30)
    assert simulation.is_mission_feasible(drone, package, sim_time) == True, "Should be feasible"
    
    # Case B: Exactly on deadline
    package.deadline = 10.0
    assert simulation.is_mission_feasible(drone, package, sim_time) == True, "Should be exactly feasible"
    
    # Case C: Impossible
    package.deadline = 9.9
    assert simulation.is_mission_feasible(drone, package, sim_time) == False, "Should be impossible"
    
    print("test_deadlines passed.")

def test_payload_energy():
    print("Running test_payload_energy...")
    time = 10.0
    energy_0 = simulation.calculate_battery_consumption(time, 0.0)
    energy_1 = simulation.calculate_battery_consumption(time, 1.0)
    energy_2_5 = simulation.calculate_battery_consumption(time, 2.5)
    assert energy_0 < energy_1 < energy_2_5, "Heavier payload should consume more energy"
    print("test_payload_energy passed.")

def test_deadline_expires():
    print("Running test_deadline_expires...")
    base_x, base_y = simulation.BASE
    drone = drone_sim.DroneState(id=1, x=base_x, y=base_y, status="IDLE")
    # Mission takes 20s. Deadline 30, remaining 30 -> Feasible.
    # At sim_time = 11, remaining 19, mission 20 -> Impossible.
    packages = {1: drone_sim.PackageState(id=1, x=base_x+1200.0, y=base_y, weight=0.0, request_time=0.0, deadline=30.0)}
    charging_pads = {1: None, 2: None, 3: None}
    
    simulation.update_package_outcomes({1: drone}, packages, 21.0)
    
    assert packages[1].status in ("REJECTED", "EXPIRED"), f"Package should be marked as impossible/expired, got {packages[1].status}"
    print("test_deadline_expires passed.")

def test_battery_degradation():
    print("Running test_battery_degradation...")
    drone = drone_sim.DroneState(id=1, x=0.0, y=0.0, battery=100.0, battery_capacity=100.0, cycle_energy=0.0)
    
    dt = 10.0
    while drone.cycle_count < 1:
        simulation.consume_battery(drone, dt)
        drone.battery = 100.0 # Refill to prevent failure
        
    assert abs(drone.battery_capacity - 99.95) < 1e-6, "Capacity should be 99.95 after 1 cycle"
    assert drone.cycle_count == 1, "Cycle count should be 1"
    
    while drone.cycle_count < 2:
        simulation.consume_battery(drone, dt)
        drone.battery = 100.0
        
    # After second cycle, it's 99.95 * 0.9995 = 99.900025
    assert abs(drone.battery_capacity - 99.900025) < 1e-6, "Capacity should degrade further"
    print("test_battery_degradation passed.")

def test_charging_logic():
    print("Running test_charging_logic...")
    drones = {}
    base_x, base_y = simulation.BASE
    for i in range(1, 5):
        drones[i] = drone_sim.DroneState(id=i, x=base_x, y=base_y, battery=18.0, battery_capacity=95.0, status="RETURNING", target=(base_x, base_y))
    
    charging_pads = {1: None, 2: None, 3: None}
    packages = {1: drone_sim.PackageState(id=1, x=0.0, y=0.0, weight=1.0, request_time=0.0, deadline=100.0)}
    for i in range(1, 5):
        drones[i].current_package = 1
        
    # Request charge
    for i in range(1, 5):
        simulation.run_simulation_step(drones[i], packages, 0.5, 0.0, charging_pads)
        
    assert drones[1].status == "CHARGING"
    assert drones[2].status == "CHARGING"
    assert drones[3].status == "CHARGING"
    assert drones[4].status == "WAITING_FOR_CHARGE"
    
    assert drones[1].charging_pad is not None
    assert drones[4].charging_pad is None
    
    pads_occupied = [d.charging_pad for d in drones.values() if d.charging_pad is not None]
    assert len(pads_occupied) == len(set(pads_occupied)), "Multiple drones on same pad!"
    assert len(pads_occupied) == 3, "Should be exactly 3 occupied pads"
    
    # Fast forward D1
    while drones[1].status == "CHARGING":
        simulation.run_simulation_step(drones[1], packages, 10.0, 0.0, charging_pads)
        
    assert abs(drones[1].battery - 95.0) < 1e-6, "Battery should charge to degraded capacity (95), not 100"
    assert drones[1].status == "IDLE"
    assert drones[1].charging_pad is None
    
    # D4 takes pad
    simulation.run_simulation_step(drones[4], packages, 0.5, 0.0, charging_pads)
    assert drones[4].status == "CHARGING"
    assert drones[4].charging_pad is not None
    print("test_charging_logic passed.")

def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(
        unittest.FunctionTestCase(fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    )


if __name__ == "__main__":
    test_movement()
    test_timestep()
    test_battery()
    test_payload()
    test_deadlines()
    test_payload_energy()
    test_deadline_expires()
    test_battery_degradation()
    test_charging_logic()
    print("All tests passed successfully!")
