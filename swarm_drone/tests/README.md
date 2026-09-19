# Tests and diagnostic scripts

These files check scheduling, physics, and fleet consistency. Most use Python's
`unittest`; `test_simulation.py` wraps its function tests for discovery.
`__init__.py` marks the test directory as a package.
Commands below are examples, not checks run as part of writing this README.

## Files

- `test_visual_playback.py`: verifies drawing between slow simulation steps,
  timing reports, and fallback from missing OpenCV Qt fonts to system fonts.
- `test_visual_workloads.py`: checks the visual hard workload's package
  volume, burst timing, seed reproducibility, visible destinations, heavy
  payloads, deadlines, low starting batteries, and configurable pressure.
- `test_assignment_modules.py`: verifies that each algorithm owns its scheduler,
  direct module calls match the assignment facade, defaults remain configurable,
  and unknown algorithm names fail clearly.
- `test_assignment_v3.py`: exercises return/pad forecasts, FIFO charging,
  soft plans, reserve and urgency behavior, return congestion/collision costs,
  and optimizer agreement with exhaustive small examples. Also checks that
  V3 works without calling V2's charging planner.
- `test_edge_cases_1_to_10.py`: impossible deadlines, overweight requests,
  coverage versus cost, competing packages, ordering/ties, busy fleets,
  occupied pads, and simultaneous low-battery returns.
- `test_edge_cases_11_to_20.py`: wind, unsafe return energy, abort/ownership
  handling, duplicate assignments, invalid telemetry, battery degradation,
  exact deadlines, stale charging preparation, and stress conditions.
- `test_invariants.py`: advances an extreme workload while checking fleet and
  package invariants. This test runs an actual simulation, not just unit mocks.
- `test_simulation.py`: nine function tests covering movement/timing, battery,
  payload, deadlines, payload energy, degradation, and charging. Can run
  directly or through `unittest` discovery.
- `test_shock_log.py`: manual diagnostic script, not an assertion-based test
  suite. Runs a 3,600-second V3 extreme simulation and prints decision histories
  for the ten initial shock packages. Its `main` guard prevents execution
  during ordinary test discovery.
- [legacy/](legacy/README.md): retained tests for removed historical APIs.

## Running selected current tests

From the repository root:

```sh
python3 -B -m unittest discover -s tests -p 'test_visual_playback.py'
python3 -B -m unittest discover -s tests -p 'test_visual_workloads.py'
python3 -B -m unittest discover -s tests -p 'test_assignment_modules.py'
python3 -B -m unittest discover -s tests -p 'test_assignment_v3.py'
python3 -B -m unittest discover -s tests -p 'test_edge_cases*.py'
python3 -B -m unittest discover -s tests -p 'test_invariants.py'
python3 -B tests/test_simulation.py
```

Run `python3 -B tests/test_shock_log.py` only when you want a new diagnostic
simulation. Plain discovery (`python3 -B -m unittest discover -s tests`)
also includes legacy tests and is not currently a fully passing suite.

The last recorded check had 61 current tests passing and 28 legacy test cases
erroring because they call missing APIs. This is a historical result, not a
fresh verification or a guarantee that every scheduler handles every edge case.
