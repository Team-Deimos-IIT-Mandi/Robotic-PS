# Assignment algorithms

Each algorithm has its own scheduler and cost-matrix builder. Applications
normally call `swarm_drone.assignment.schedule_packages` rather than selecting
these modules directly. Names accepted by that facade are `baseline`, `v1`,
`v2`, and `v3`.

## Files and behavior

- `__init__.py`: marks this directory as an importable subpackage.
- `baseline.py`: evaluates idle-drone candidates and selects the lowest-cost
  feasible candidate separately for each pending package. It uses V1's weighted
  cost but does not perform the global one-drone-per-package matching search.
- `v1.py`: builds candidates from idle drones and uses the shared optimizer
  to select a global matching. Candidate costs include a charging-risk penalty.
- `v2.py`: adds waiting and charging drones to the allowed states. First calls
  `charging.manage_charging_infrastructure`, which uses fleet preparation plans,
  then builds the matrix and performs global matching. Charging is handled
  structurally rather than through V1's charging-risk cost term.
- `v3.py`: predicts future availability for idle, waiting, charging, delivering,
  and returning drones. Estimates return, pad wait, charging, dispatch, and
  arrival times; ranks candidates with predictive costs. Keeps a dynamic reserve
  for ordinary immediate departures and allows urgent dispatch to use it.
  Ready selections dispatch physically; future selections become soft
  `preparation_package` plans, not immediate package ownership.
- `v3_charging.py`: V3's forecasting and live charging implementation. Projects
  battery at base, derives package charge targets, estimates shared-pad waits
  and return charging congestion, and starts live waiters in FIFO order with
  drone ID as the tie-break. Defines V3 reserve and urgency policy constants.
- `common.py`: validates/rejects/expires requests, checks ordinary candidates,
  builds candidate matrices and decision logs, and commits dispatches through
  `fsm.assign_package`. Shared by multiple algorithms.
- `optimizer.py`: bounded recursive search for package/drone matching, with at
  most one selected package per drone. Maximizes coverage first. V1/V2 then
  favor minimum slack, total slack, and lower cost. V3's `cost_first=True`
  mode favors urgent coverage, lower predictive cost, then slack. Search has
  a 50,000-step cap, so large instances are not guaranteed exhaustive optima.

V3 does **not** call V2's `manage_charging_infrastructure` or
`plan_fleet_preparation`. It calls its own `_execute_v3_charging` before and
after selection. Predictions are recomputed as the fleet changes; a future
forecast does not teleport a busy drone or assign it a second physical mission.

## Calling the scheduler

```python
from swarm_drone import assignment

assignment.schedule_packages(drones, packages, sim_time, charging_pads, "v3")
```

`drones` and `packages` are dictionaries keyed by IDs; `charging_pads` maps
pad IDs to drone IDs or `None`. Scheduling mutates these states and package
decision histories. V3 additionally accepts `reserve_fraction` and
`min_reserve`; `min_reserve=0` disables the ordinary departure reserve.

For existing measurements without new simulations, use
`python3 -B scripts/analysis.py` from the repository root. Algorithm regression
coverage is described in [tests](../../tests/README.md). Historical benchmark
results are measurements for particular workloads, not general guarantees.
