# V3 hybrid scheduling results

Measured on 2026-09-17, using 10 drones, 3 charging pads, 3,600 simulated seconds,
1-second steps, deterministic initial batteries (seed 123), and identical
package manifests and wind seeds before and after the changes. Before means
the predictive V3 implementation at the start of this task.

| Workload | Seed | Requests | Previous V3 on time | Hybrid V3 on time |
| --- | ---: | ---: | ---: | ---: |
| Extreme | 42 | 36 | 32 | 34 |
| Extreme | 99 | 99 | 76 | 81 |
| Extreme | 7 | 101 | 80 | 81 |
| HARD, one request every 10 seconds | 42 | 360 | 360 | 360 |

Seed 42 contains two physically impossible requests. Hybrid V3 delivered all
34 feasible requests on time: 100%, compared with the previous V3's 94.1%.
The other extreme rows show counts against all requests, including impossible
requests. All final V3 runs ended with no pending, assigned, expired, or late
packages, and no failed drones; the remaining packages were rejected.

| Final V3 run | Peak waiting queue | Peak airborne | Total charging wait, seconds |
| --- | ---: | ---: | ---: |
| Extreme, seed 42 | 0 | 7 | 6.3 |
| Extreme, seed 99 | 4 | 9 | 605.0 |
| Extreme, seed 7 | 3 | 8 | 216.2 |
| HARD, seed 42 | 0 | 2 | 66.7 |

These runs do not demonstrate elimination of the charging bottleneck. Queue
length is sampled before and after each simulation step; fractional waits
also contribute to total charging wait. The HARD workload is already at
100% delivery success for every algorithm in this simulator. In the final
seed-42 extreme comparison, V2 delivered 32 of 34 feasible requests, while
hybrid V3 delivered 34. V2's charging wait was 1.5 seconds versus V3's 6.3:
the policy improves deliveries here, not every charging metric.

## Implemented policy

- Keep two usable drones available for ordinary dispatch, with a smaller
  effective reserve for small or damaged fleets. Usable means empty, at base,
  available, and holding at least 20% battery capacity. Drone identities are
  not permanently reserved. `min_reserve=0` disables the reserve constraint.
- A package is urgent when its earliest feasible predicted delivery leaves
  at most 15 seconds of deadline slack. Urgent dispatch may consume reserve
  capacity and tolerate charging congestion.
- Forecast each new mission's return time, battery, charging demand, and pad
  wait. Defer ordinary immediate dispatch that needs return charging when
  projected demand is at least twice the pad count and return pad wait exceeds
  60 seconds.
- Add positive charging-congestion and return-collision costs because the
  optimizer minimizes cost. Return clustering uses a 30-second window; urgent
  packages receive one quarter of these penalties.
- Optimize coverage, then urgent coverage, then predictive cost, then slack.
  Preserve the legacy optimizer ordering for other algorithms. Use reserve-aware
  bounds, relaxed cost bounds, and repeated-state pruning.
- No fixed departure interval or three-drone launch limit.

## Reproduce

```sh
python3 scripts/run_extreme_workload.py --seed 42 --no-traces
python3 scripts/run_extreme_workload.py --seed 99 --no-traces
python3 scripts/run_extreme_workload.py --seed 7 --no-traces
python3 scripts/run_extreme_workload.py --workload hard --no-traces
```

## Verification

26 V3 tests and 21 existing edge-case/invariant tests passed. The V3 tests
include reserve enforcement, urgent overrides, saturation deferral, return
clustering, package-level urgency, and comparison of the optimized search
against exhaustive small assignments. All workload steps ran fleet validation.
Python compilation passed. `assignment.py` contains no comments.

The repository-wide whitespace check still reports pre-existing trailing
whitespace in the user's modified `simulation.py`; that file was not edited.
