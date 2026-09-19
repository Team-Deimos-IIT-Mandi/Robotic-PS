# Simulator package

This folder contains the reusable simulator code. Import it as a package,
for example `from swarm_drone import simulation, assignment`.
Run the commands below from the repository root, not from this folder.

## Files

- `__init__.py`: marks the folder as the Python package `swarm_drone`.
- `assignment.py`: the shared scheduling entry point. Routes algorithm names
  (`baseline`, `v1`, `v2`, `v3`) to their implementations and exposes shared
  candidate, matrix, and V3 forecasting helpers.
- `simulation.py`: initializes drones, creates HARD requests, advances drone
  states, checks telemetry and fleet consistency, updates package outcomes,
  and saves JSON decision reports. Also provides the main simulation CLI.
- `drone_sim.py`: defines `DroneState`, `PackageState`, base/map coordinates,
  and the OpenCV renderer. Rendering displays state; it does not schedule
  packages or autonomously move drones.
- `physics.py`: movement with wind, pixel/meter conversion, payload-dependent
  speed, delivery/round-trip estimates, and battery calculations.
  `calculate_battery_consumption(time, payload)` is defined here.
- `fsm.py`: physical mission transitions: assignment, abort, delivery, and
  return to base. This is not the removed legacy rule-based scheduling API.
- `charging.py`: physical charging, pad allocation, battery degradation,
  and V2's `manage_charging_infrastructure`/`plan_fleet_preparation` functions.
- `telemetry.py`: estimates remaining delivery and return energy under wind;
  returns `SAFE`, `CAUTION`, or `ABORT` with a reason and diagnostic values.
- `wind.py`: generates seeded wind events and evaluates local wind vectors.
- `paths.py`: derives the repository root from its own location and defines
  portable default result, log, and benchmark directories.
- [assignment_algorithms/](assignment_algorithms/README.md): the four schedulers,
  shared dispatch helpers, optimizer, and V3 charging forecasts.
- [assignment_costs/](assignment_costs/README.md): feature extraction and the
  scoring functions used by baseline, V1, and V2.

## How the parts work together

The simulation creates requests and invokes `assignment.schedule_packages`.
The selected scheduler evaluates candidates and dispatches ready drones through
`fsm`. The simulation then advances movement/charging using `physics` and
`charging`, checks mission telemetry, and updates package outcomes. The renderer
can display the resulting state; reports record package decisions and outcomes.

## Usage

```sh
python3 -B -m swarm_drone.simulation
python3 -B -m swarm_drone.simulation --algorithm v3
python3 -B -m swarm_drone.simulation --headless --minutes 1 --algorithm v2
```

These commands run new simulations and save reports under `results/logs/`,
recreating that directory if needed. The simulation CLI supports baseline,
V1, V2, and V3. For a visual V3 tester, run
`python3 -B scripts/run_v3_visual.py`; it defaults to 40 simulated minutes
in about eight real minutes. See [scripts](../scripts/README.md).

Coordinates are generally pixels; physics converts distances to meters when
estimating travel. Battery depletion is a simulator battery quantity, not a
measurement in watt-hours. `-B` prevents bytecode-cache generation.
