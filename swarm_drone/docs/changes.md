# Drone Fleet Management: Project Evolution & Solutions

This document details the progression of the Drone Fleet Simulator project, outlining the specific problems encountered at each stage and the algorithmic solutions applied to solve them.

**Current implementation:** Section 12 updates reserve consistency, evaluation,
and multi-job throughput planning. Section 11 introduced future-available drones.
These supersede the independent per-drone prediction in Sections 5 and 7.
Earlier experimental numbers are
historical; they do not establish the performance of the new fleet planner.
In particular, status-based waiting metrics cannot establish fair V1/V2
charging-wait comparisons.

## 1. Establishing the Foundation: The Baseline Simulator
**The Problem:**
Before building a complex scheduler, we needed a reliable testing environment. The initial simulator only handled basic drone physics (movement, battery drain) for a single drone. We lacked a way to test fleet-wide behaviors, continuous package arrivals, and shared charging infrastructure.

**The Solution:**
- Scaled the simulator to a 10-drone fleet running concurrently.
- Introduced a central server logic (`assign_packages_baseline`) that assigned the next available package to the first `IDLE` drone that could feasibly complete it.
- **Result:** The baseline worked but exposed severe operational flaws. Drone 1 ended up doing most of the work while Drone 10 sat idle, leading to fleet imbalance and uneven battery degradation.

---

## 2. Scheduler V1: Fleet Balance & Weighted Scoring
**The Problem:**
The baseline assignment algorithm was fundamentally unfair, causing uneven wear-and-tear on the fleet (the "fleet-imbalance behavior" warned about in the project specifications). 

**The Solution:**
- Replaced the baseline assignment with a **Weighted Cost Scheduler (V1)**.
- For every new package, the scheduler evaluated all feasible idle drones.
- It calculated a score based on distance, deadline urgency, and a new **utilization penalty**.
- **Result:** The workload was distributed across the 10 drones. However, running a stress test (64 packages in 10 minutes) revealed a deeper, more systemic problem: massive queues formed at the charging station, with drones waiting over 6 minutes to access one of the 3 charging pads.

---

## 3. Identifying the True Bottleneck: Physical Constraints
**The Problem:**
We needed to determine if our V1 algorithm was flawed, or if the system was physically starved. We ran experiments varying the number of charging pads (3, 5, 7, 10). 

**The Solution:**
- The data provided strong evidence that with 10 pads, the V1 scheduler achieved zero observed charging wait under the tested workload.
- This provided a critical insight: **The primary limiting factor of the fleet was not the assignment algorithm, but physical charging congestion.** The 3 charging pads were the true bottleneck.

---

## 4. The "Backfire" Insight: Expected Wait Time & Full Charging
**The Problem:**
We modified the scheduler to predict charging queue wait times and penalize assignments that would dump a drone into a traffic jam. Furthermore, we allowed drones to proactively charge if a pad was free before the rush hit.

**The Solution & Insight:**
We built a forward-looking queue simulator, but the standard charging logic forced drones to charge to 100%. The experimental timeline revealed a critical failure mode:

```text
t = 0
3 drones start proactively charging

40-minute full-charge requirement
        ↓
3 pads occupied for entire 10-minute experiment
        ↓
other drones cannot charge
        ↓
fleet becomes progressively depleted
        ↓
throughput collapses
```

- **Result:** Package throughput collapsed. We observed that initiating a massive 30-minute charge cycle right before a 10-minute surge in demand effectively locked the fleet out of the infrastructure.

---

## 5. Scheduler V2: Predictive Partial Charging
**The Problem:**
We needed an algorithm that actively managed the charging infrastructure as a constrained resource, rather than passively reacting to it. Drones needed to charge only what they needed, when they needed it.

**The Solution:**
We implemented a 3-stage receding-horizon fleet management algorithm:
1. **Continuous Charging Physics:** We rewrote the simulator so drones charge continuously per tick and automatically disconnect when they hit a dynamic target.
2. **Predictive Target (Stages 1 & 2):** For every idle/charging drone, the scheduler scans the pending package queue, identifies the most urgent feasible mission, calculates its required energy, and adds a flat 10% safety margin to define a custom `target_battery`.
3. **Infrastructure Management (Stage 3):** The scheduler actively kicks fully-charged drones off the pads and sorts waiting drones by how urgently they need power for their next predicted mission.

---

## 6. V2 Evaluation

To make a scientifically meaningful comparison, we ran a controlled experiment maintaining strict constants:
- Same number of drones
- Same package arrival pattern
- Same package locations and weights
- Same simulation duration (10 minutes)
- Same charging-pad count (3 pads)
- *Only the scheduling/charging policy changed*

**Metrics Analyzed:**
- Packages delivered
- Packages missed
- Average charging wait
- Maximum charging wait
- Average drone utilization
- Utilization variance
- Energy consumed
- Pad utilization

**The Result:**
Testing V2 against the Baseline under extreme charging contention yielded substantial improvements:

| Metric | Baseline | V2 (Predictive Partial) | Improvement |
| :--- | :---: | :---: | :---: |
| **Packages Delivered** | 42 | **63** | Improved package throughput by 50% |
| **Max Charging Wait** | 484.2s | **99.8s** | Reduced peak wait times significantly |
| **Pad Utilization** | ~95% | **~38%** | Relieved infrastructural pressure |

### Why V2 Reduces Pad Utilization
The mechanism driving these results is the shift from full to partial charging:

```text
Charge to 100%
      ↓
Long pad occupancy
      ↓
Long charging queues

Partial predictive charging
      ↓
Shorter charging sessions
      ↓
Pads released sooner
      ↓
More drones can access pads
      ↓
Less waiting
```

---

## 7. V2.1 Optimization: Opportunistic Charging

While V2 solved the charging blockage, it introduced a new inefficiency: when demand dropped and pads were free, drones were capped at their immediate target battery. The charging infrastructure sat idle instead of being used to build up energy reserves for future surges.

**The Solution (Hierarchical Demand-Aware Policy):**
We implemented an opportunistic charging algorithm that continually categorizes drones and preempts pad access based on real-time fleet urgency.

- **Essential Demand:** Drone needs charge for a specific urgent mission (`predicted_slack <= 60s`). Gets highest priority for a pad. Charges only to `required_energy + 10%`, then yields the pad.
- **Opportunistic Demand:** Drone has no urgent missions but `battery < 100%`. It claims free pads and charges toward 100% to prepare for future surges, but will **instantly surrender the pad** if an Essential drone appears.

**The Result:**
Testing V2.1 completely revolutionized system performance. To understand whether opportunistic charging truly matters specifically under constrained infrastructure, we tested both V2 and V2.1 across varying pad counts:

| Pads | V2 Max Wait | V2.1 Max Wait | V2 Avg Wait | V2.1 Avg Wait |
| :---: | :---: | :---: | :---: | :---: |
| **3** | 48.7s | **7.5s** | 15.5s | **3.1s** |
| **5** | 16.3s | **1.8s** | 3.8s | **0.5s** |
| **7** | 2.6s | **0.8s** | 1.4s | **0.2s** |
| **10** | 2.6s | **0.2s** | 1.4s | **0.0s** |

*(Note: Both V2 and V2.1 successfully delivered 64/64 packages in this configuration, moving the metric of interest entirely to wait-time efficiency).*

### The Infrastructure Hypothesis Verified
The data perfectly demonstrates the advantage of opportunistic preemption:
- **Under high contention (3 pads):** V2.1 provides a massive advantage, dropping max wait times by over 80%.
- **Under low contention (10 pads):** The advantage shrinks to near-zero, because there is no contention to manage.

V2.1 safely pushes pad utilization to 100% by exploiting idle capacity for future readiness, solving the unused-capacity problem while maintaining incredibly low queueing times.

---

## 8. Limitations & Future Improvements

While V2.1 maximized system throughput, the algorithm uses heuristics that present clear limitations:
- **Myopic Prediction:** The next-mission prediction is based only on currently known packages in the queue.
- **Fixed Safety Margins:** The 10% battery safety margin is fixed rather than adaptive.
- **Dynamic Invalidation:** Unexpected package arrivals can invalidate the predicted target mid-charge.
- **No Global Optimization:** The scheduler does not globally optimize the entire 10-minute horizon, prioritizing immediate routing.

### Proposed Improvement: Adaptive Safety Margins
Currently, the target battery is calculated as:
`target battery = required battery × 1.10`

A stronger algorithmic contribution would be an adaptive margin that responds to system uncertainty:
`target battery = required battery × (1 + adaptive_margin)`

- **Low workload / predictable:** 10% margin
- **High workload / uncertain:** 15–20% margin
- **Very high congestion:** 20–25% margin

---

## 9. System-Level Conclusion

The evolution of the project reflects a shift in scale and complexity:

```text
V0 (Basic drone simulation)
        ↓
Baseline (First-feasible assignment)
        ↓
V1 (Multi-objective drone assignment)
        ↓
Experimentation (Discover charging infrastructure bottleneck)
        ↓
Failed approach (Predictive queue + full charging)
        ↓
V2 (Predictive partial charging)
        ↓
V2.1 (Opportunistic pad preemption)
        ↓
Fleet-level resource management
```

**Conclusion:** The scheduler evolved from simply selecting drones for packages, to actively managing the complex interaction between drones, pending missions, physical battery state, and the shared charging infrastructure.

---

## 10. Coordinated Fleet Charging Preparation

### Problem addressed

The previous `predict_mission_needs()` ran independently for each drone. Several
drones could select the same pending package and prepare duplicate capacity,
while other packages received no preparation. It also filtered candidates by
current battery, excluding the very jobs for which charging was necessary.

### Implemented behavior

- `plan_fleet_preparation()` now considers the pending queue and available
  drones together. Only empty, available drones physically at the base are
  eligible; airborne, failed, and already assigned drones are excluded.
- Pending packages are processed by earliest deadline, then request time and
  package ID. Each package is paired with at most one drone, and each drone
  prepares for at most one next package in a planning pass.
- Candidate feasibility includes return-flight energy, degraded capacity,
  charging time, predicted waiting for a shared pad, and delivery arrival time.
  A drone may be selected even when its current battery cannot fly the mission.
- The existing reserve formula is retained:
  `target = min(round_trip_energy + 0.10 * current_capacity, current_capacity)`.
  This is an additive reserve based on capacity, not `mission_energy * 1.10`.
- A shared pad calendar reserves non-overlapping predicted charging intervals.
  For each package, the planner chooses the earliest achievable arrival; ties
  use added charging energy, accumulated flight time, and drone ID.
- `manage_charging_infrastructure()` starts the head of each pad queue and
  allows unpaired drones to top up on unused pads. Opportunistic sessions can
  be preempted for planned demand. Pad ownership changes are committed together
  to preserve consistency when drones move between pads.
- V2 dispatch uses the same plan and waits until the selected drone reaches
  its preparation target. It cannot take another package's prepared drone.
  Baseline and V1 assignment behavior is unchanged.
- Preparation is temporary: it does not set `package.assigned_drone`. The plan
  is rebuilt every scheduling tick, so cancellation, expiry, new arrivals, or
  battery changes can release or alter a pairing. Physical ownership starts
  only on dispatch.
- Existing decision reports now include V2's selected preparation, candidate
  alternatives, target energy, pad interval, and predicted arrival. Existing
  weighted score components remain diagnostic; the fleet preparation pairing
  determines V2's selected drone.

### Example

With three pending packages and three eligible drones, the planner can prepare
`D1 -> P1`, `D2 -> P2`, and `D3 -> P3`, rather than preparing all three for P1.
If only one pad exists, the predicted charging sessions occur sequentially.
A pairing is omitted when that waiting time makes its deadline unreachable.
An omitted pairing does not itself reject the package; normal request outcome
handling still controls rejection and expiry.

### Scope and limitations

Distances, request generation, simulation duration, playback speed, battery
physics, and benchmark metrics were not changed by this update. It does not
implement the separately discussed waiting-metric corrections.

This is a deterministic, greedy fleet heuristic, not a global optimizer or a
proof that every feasible package can be served. It plans only one next mission
per currently available drone. Future returning drones, unknown requests, and
multi-job routes are not forecast. Replanning can change a pairing; no switching
penalty or guaranteed starvation prevention is implemented. The simulator still
assumes immediate pad preemption with no physical pad-transfer delay. Timing
predictions are continuous estimates, while execution uses the caller's time
step, so exact-boundary deadlines can be sensitive to simulation resolution.

### Verification

Added `tests/test_fleet_preparation.py` with 12 passing tests covering unique
pairings, energy-deficient candidates, shared-pad queue timing, infeasible
deadlines after charging, no-pad behavior, dispatch consistency, end-to-end
charging and delivery, invalidated plans, opportunistic preemption, degraded
capacity, pad invariants, and excluded airborne/future/invalid candidates.

Before this update, the existing suite already failed `test_deadlines`,
`test_deadline_expires`, and `test_charging_logic`. Those older tests were left
unchanged; their failures must not be interpreted as new regression results.

The unchanged 100-minute random workload also completed with seed 42 and fleet
invariant checks enabled (about 23 seconds of headless computation). This is
an integration check, not evidence of superiority over V1: the workload's
existing aggregate outcome and status-based wait reporting still has the
previously identified evaluation limitations.

---

## 11. Future Fleet Availability, Shared Scheduling, and Stable Preparation

### Why this change was needed

The base-only planner could miss a package that a returning drone could serve
without charging. It could also plan unnecessary charging for a drone whose
current target was higher than the next mission needed. Future reservations
require both a forecast and strict separation from physical execution.

### Future state prediction

`predict_drone_availability()` forecasts an empty drone at the base using a copy
of its state. Idle, waiting, and charging drones at base are available now with
their actual stored energy; existing charging targets are preemptible.
Returning drones finish their remaining return leg. Delivering drones finish
their current package with its current payload, then return empty. The current
package owner and live drone state are never changed by forecasting.

The forecast includes energy consumption and cycle-based capacity degradation.
Whole-leg predictions conservatively subtract the capacity lost on each leg
in addition to the existing consumption calculation, bounding a possible
earlier capacity clamp in the physical time-step execution. Unsafe returns,
failed drones, invalid telemetry, and inconsistent current missions are not
future candidates. New-mission distances and energy always use the predicted
base position, not the live airborne position.

The physical flight and charging rates remain unchanged. In particular, adding
25% of usable capacity takes 600 simulated seconds with a 40-minute recharge,
regardless of playback speed. The reserve formula remains the capped additive
10%-of-capacity policy from Section 10.

### Coupled matching and charging intervals

The planner builds candidates from predicted availability, battery and capacity.
Every proposed pairing is evaluated against a shared calendar of charging-pad
intervals. Charging cannot start before the drone returns. The planner searches
free gaps between reservations, so an early-arriving drone can use a pad before
a later reservation. Drones with sufficient energy require no pad reservation.

A bounded beam search keeps six alternative partial matchings and their
calendars while processing packages in deadline order. This lets it reconsider
an early drone choice when another pairing covers more packages. Its ranking is:

1. More packages covered by the current plan.
2. Earlier total package deadlines for equal coverage.
3. Lower total predicted arrival delay plus switching penalties.
4. Lower additional charging energy, then accumulated flight time and stable IDs.

This is a bounded heuristic, not a global optimizer or throughput guarantee.
It still plans one next package per drone, excludes unknown future requests,
and may miss better arrangements outside the retained alternatives.

### Reservation stability

Each drone stores only the ID of its temporary preparation package. Changing a
still-relevant pairing adds five simulated seconds to the arrival-cost ranking.
Thus small arrival improvements do not normally cause switching; extra package
coverage or a sufficiently better feasible plan can override the preference.
Invalid or completed reservations are cleared when replanning. This is a
tunable heuristic, not a physical delay or irreversible lock.

### Physical execution and timing

Actual charging and package dispatch still require an empty, eligible drone
physically at base. Future preparation only changes reservation metadata on
airborne drones; it never changes their current mission or puts them on a pad.
Opportunistic charging can fill gaps, with targets limited to the next reserved
start. V2-managed waiting drones no longer autonomously take any free pad from
inside `update_drone()`; the manager controls their pad access. Baseline and V1
retain their previous charging-entry behavior.

All schedulers accept an optional `timestep` argument, defaulting to one second
for existing callers. The visual runner passes its actual 0.25-second step;
both workload runners pass their existing one-second step. Predicted return
availability and charging completion are rounded up to the next scheduler tick
before evaluating the delivery deadline. Rates, distances, durations, seeds,
arrival generation and metric definitions were not changed.

Decision reports include forecast availability, battery/capacity at base,
charging duration, pad intervals, alternatives, and predicted delivery arrival.
Existing wait/outcome reporting limitations in the workload harness are outside
this change and still prevent unsupported algorithm superiority claims.

### Verification

`tests/test_future_preparation.py` adds 16 passing tests covering read-only return
forecasting, current-job completion before a next job, preemptible charging,
correct charging units, no-charge future missions, airborne execution guards,
shared-pad gaps, reconsidered matching for coverage, reservation stability and
release, unsafe return exclusion, degradation, scheduler-tick boundaries,
end-to-end return/charge/dispatch/delivery, controlled waiting, and opportunistic
charging yielding to a future reservation.

The existing 100-minute random workload completed with seed 42 in about 18
seconds of headless computation. The saved report accounted for all 642
packages: 216 on-time, 0 late, 412 rejected, 0 expired, 11 pending and 3 assigned.
These are integration results, not proof of throughput improvement. The older
`test_deadlines`, `test_deadline_expires`, and `test_charging_logic` still fail
as before; they were not altered in this update.

---

## 12. Fair Evaluation and Throughput-Oriented Planning

### Common safety constraint

Baseline, V1, and V2 now all require round-trip mission energy plus 10% of the
drone's current usable capacity before dispatch. `mission_departure_energy()`
defines that rule once for feasibility checks, candidate reporting, and V2
charging targets. A mission that cannot fit this full reserve within capacity
is infeasible; unlike the older V2 formula, the reserve is not silently reduced
by capping the departure target. The 10% value is a shared conservative policy
parameter, not a claim of experimentally optimized or real-flight safety.

V1's earlier ability to depart without this reserve made its throughput an
unequal comparison. New results must not be compared directly with older
V1 results without acknowledging this changed safety requirement.

### Consistent wait episodes and outcomes

The random workload uses the same physical low-battery predicate as the V2
fairness monitor: empty at the base, no current package, battery below 20% of
current capacity, and drone ID absent from the charging-pad occupancy map.
`IDLE`, `WAITING_FOR_CHARGE`, and `CHARGING` labels do not define the metric.
Airborne/busy drones and failed drones are excluded. This measures low-battery
waiting, not proof that no delivery could be performed.

Wait episodes store start, end, duration, and whether the interval was still
ongoing at experiment end. Reports include cumulative wait per drone, longest
observed individual episode, mean total wait across drones, and the worst
observed episode across runs. State is observed before and after scheduling at
the same timestamp and at each physical step boundary. Boundaries and pad
utilization are sampled at one-second resolution; unfinished intervals remain
censored observations rather than claims of completed queue waits.

All six outcomes come from `summarize_packages()`: on-time, late, rejected,
expired, pending and assigned/in-flight. Counts must sum to generated requests.
Energy use is read from accumulated discharge/cycle counters rather than net
battery change across ticks that may also contain charging. Final stored energy,
flight time, pad utilization and failed-drone IDs are included for interpretation.

### Reproducible paired evaluation

`run_random_workload.py` defaults to seeds 42, 100 and 2026. For each seed it
generates one immutable request/initial-battery workload using a local RNG, then
replays copies for Baseline, V1 and V2. The RNG draw order and distributions from
the original workload are preserved. A workload fingerprint is checked across
policies to verify they received identical requests and starting batteries.

Output includes per-seed results, means and sample standard deviations, the
worst observed waiting episode, and paired V2-minus-V1 on-time differences.
Three seeds provide an initial reproducibility check, not proof of statistical
significance. A unique benchmark JSON preserves results and per-drone episodes;
detailed decision logs are enabled by default. `--no-decision-logs` omits those
bulky histories during evaluation without changing decisions. Errors writing
reports are no longer silently swallowed.

### Multi-job planning objective

Each V2 beam branch now projects up to three successive jobs per drone. Every
job includes charging, delivery, empty return, energy use, degradation and the
next tick when the drone can depart again. Shared-pad intervals across the
whole branch cannot overlap. Only each drone's first job is executable; later
jobs are forecasts which will be reconsidered at the next scheduling tick.

The rank maximizes the number of predicted on-time jobs first, then minimizes:

`sum(charging_seconds / pad_count + mission_seconds / drone_count)`

plus a smaller arrival-delay/stability term:

`0.05 * (sum(predicted_arrival - now) + 5 seconds per changed first pairing)`.

Earlier deadlines, accumulated flight time and stable IDs break remaining ties.
Charging and flight resource consumption therefore influence decisions directly,
rather than being subordinate to the sum of deadlines. An explicit skip branch
is retained so one expensive early package need not eliminate the alternative
of serving several shorter jobs. The six-branch search and three-job horizon
are bounded heuristics, not an optimal plan or a guarantee of improved throughput.

### Fairness safeguard

V2 gives recovery charging priority after a continuous low-battery base wait
reaches 600 simulated seconds. Recovery proceeds to 20% of current capacity,
reserving that pad time before delivery planning and remaining active across
ticks until complete. Mission dispatch cannot interrupt recovery below its
service target. Opportunistic or planned preparation uses the remaining capacity.

The 600-second value is a configurable intervention threshold, not a guaranteed
maximum wait: simultaneous overdue drones can exceed it when pads are occupied
by other recovery sessions. The safeguard addresses starvation without requiring
equal charging durations, and may trade some throughput for service fairness.
Baseline and V1 do not acquire this V2 scheduling rule; they do receive the same
safety reserve and are measured with the same waiting definition.

### Scope and verification

Physical rates, workload duration (100 minutes), distances (3000-6000 pixels),
request frequency/weight/slack distributions, starting battery distribution,
fleet size, pad count, and simulation step are unchanged. Only the requested
reserve, scheduling, measurement, and evaluation behavior changed.

The 16 future-preparation tests were retained and adapted where one-job-only
assumptions no longer apply. Eleven new tests cover reserve equality, infeasible
reserves, airborne exclusion, pad-map-based waits, episode censoring, sequential
multi-job energy/time, skipping expensive jobs, recovery continuity, dispatch
guards, deterministic workloads, and outcome reconciliation: 27 focused tests
pass. Historical tests outside these changes are reported separately.

### Fixed-seed results (42, 100, 2026)

All nine 100-minute runs completed with matching workload fingerprints and zero
failed drones or late deliveries. Decision-history serialization was disabled
for these validation runs; the saved benchmark JSON retains all outcome counts,
per-drone wait episodes, censoring flags, and aggregate metrics.

| Policy | On-time, mean +/- sample SD | Worst observed single wait |
| --- | ---: | ---: |
| Baseline | 116.67 +/- 1.53 | 5741 s |
| V1 | 221.33 +/- 1.53 | 5648 s |
| V2 | 220.00 +/- 1.00 | 600 s |

The paired V2-minus-V1 differences were -1, -2 and -1 deliveries. V2 therefore
remained slightly below V1 on throughput (about 0.6% on these means), while
reducing the worst observed low-battery episode substantially. These results
do not establish V2 throughput superiority or a universal 600-second bound.
No parameter tuning was performed against these seeds after observing results.

The 40-minute graphical-runner simulation path also completed headlessly at
its 0.25-second step with all 240 requests on time and no failed drones.
The three historical failures (`test_deadlines`, `test_deadline_expires`,
`test_charging_logic`) remain unchanged. The 27 focused tests passed.

## 13. Delivery-focused recovery, ordering, beam diversity and spare charging

Implemented the four requested V2 improvements and documented them in README.md.
This section supersedes Section 12's fixed-20% mission-recovery behavior.

- Recovery after 600 seconds of low-battery waiting now chooses a distinct,
  deadline-feasible pending delivery for each serviced drone. Its target is the
  full round-trip energy plus the unchanged common safety reserve. A ready drone
  needs no pad and may depart below 20%. The recovery pairing remains preferred
  while feasible and is released on dispatch or invalidation. If no suitable
  pending job exists, recovery still charges to 20%.
- Recovery mission heads are included in the fleet forecast before ordinary
  planning, so their packages and pad intervals cannot be double-booked.
- The bounded three-job planner tries insertion at every position in a retained
  drone route, recalculating energy, degradation, delivery/return times and shared
  charging slots. Recovery heads stay fixed until dispatched or invalidated;
  other drones' existing forecast intervals are protected during each trial.
- The six-plan beam deduplicates exact routes, retains the best plan and the best
  skip alternative, and prioritizes competitive, structurally distinct plans.
  Strategy signatures ignore drone/pad labels and bucket charging durations and
  starts into simulated-minute intervals. A diverse candidate must cover the
  same number of jobs as the best and have resource/delay cost no more than the
  best plus `max(10, 0.25 * abs(best_cost))`. Remaining slots use the normal rank.
  These bounds are heuristics, not an exhaustive permutation search.
- Optional charging ranks drones by time to useful readiness. Uncovered feasible
  pending requests supply the first-choice target; otherwise the median mission
  target from up to 50 already-observed requests supplies an estimate, with 20%
  fallback. Under-target drones precede already-ready top-ups. Targets are capped
  by the next reservation on the selected pad, including later forecast jobs.
- Drone metadata records recovery package and charging basis, exposed in package
  decision reports. No future arrivals are used as prediction input, and all
  actual dispatches retain the normal energy and deadline checks.

All physical parameters, workload distributions, three fixed seeds, safety
reserve and the common physical waiting metric remain unchanged. Baseline and
V1 scheduling are unchanged. No month-long simulation was run.

### Regression verification

Twelve additional tests cover the new behavior, and the old fixed-20% dispatch
test now checks the safe mission-specific target. All 39 focused unittest tests
pass. Six of nine historical function-style tests pass; the same three legacy
failures recorded in Section 12 remain, with no edits to that test file.

### Unchanged-workload comparison after implementation

All nine 100-minute runs completed for seeds 42, 100 and 2026. Workload
fingerprints match both the other policies and Section 12's earlier runs.
Baseline and V1 outcomes are unchanged. Every run had zero failed drones and
zero late deliveries.

| Policy | On-time, mean +/- sample SD | Worst observed single wait |
| --- | ---: | ---: |
| Baseline | 116.67 +/- 1.53 | 5741 s |
| V1 | 221.33 +/- 1.53 | 5648 s |
| Updated V2 | 219.33 +/- 1.15 | 600 s |

Updated V2 delivered 220, 220 and 218 packages on time. Its paired differences
from V1 were -1, -3 and -2. The earlier V2 delivered 220, 221 and 219 on the same
seeds, so the new mean is lower by 0.67 deliveries, not an improvement. The new
behaviors work in the regression scenarios but have not demonstrated a stress
throughput benefit. This result is retained without seed-specific tuning.

The comparison report is `benchmark-20260914T123838328935Z.json` under the task's
`outputs/fleet-comparison-improvements/` folder. The 40-minute demo also completed
headlessly at the unchanged 0.25-second step in 14.1 wall-clock seconds, with all
240 packages on time and no failed drones; graphical playback was not exercised.

## 14. Separate rule-based assignment FSM

Built on the user's unfinished `AssignmentState` enum. Added an opt-in `fsm`
policy, while retaining the `v2` default. Restored the disabled V1/V2 feature,
score and selection code so both comparison modes can assign packages again.
The original physical drone states and flight/charging calculations were not
rewritten. Fleet size, pad count, distances, deadlines, workloads, reserve and
playback settings are unchanged.

The assignment FSM has explicit allowed transitions and a trace for every
decision attempt. Validation, feasibility, readiness, urgency, selection,
preparation, assignment and waiting are separate states. Each scheduler tick
retries pending packages; rejected and expired requests leave the waiting flow.
Already assigned packages retain their physical owner. Candidate plans are
dictionaries addressed by drone ID, matching the scheduler's actual data format.

The FSM owns normal drone selection instead of receiving the single pair already
selected by V2. It does not invoke either weighted score function or V2's beam
planner. The shared charging executor was extracted into `apply_charging_plan()`;
it follows the supplied pairings and reservations. V2 still supplies its own
original plans to that executor. The existing explicit starvation-recovery rule
is reused before normal FSM decisions, including mission-specific recovery
targets and the 20% fallback when no suitable delivery exists.

Requests are ordered by spare time after the earliest safe arrival, with recovery
reservations first. Ready drones are preferred over future options. Critical
means at most one scheduling step of spare time, not an arbitrary 20/40 seconds.
Critical requests use earliest safe arrival. Normal requests first preserve a
drone uniquely needed by another pending package, then prefer earliest arrival.
Remaining ties use overdue low-battery waiting, accumulated flight time, excess
battery and stable drone ID. These are ordered rules, not a weighted cost sum.

The FSM can prepare one next job per drone, including future return and charging
time. Preparation does not transfer package ownership. Actual dispatch rechecks
physical readiness, battery reserve, payload, deadline and pad ownership, releases
the pad and commits the assignment synchronously. Tests cover conflicting
requests, duplicate ticks, changed requests, busy pads and departure directly
from charging. This is a greedy rule-based policy, not an optimal matching or a
complete server/client fault-handling FSM.

Added `--algorithm fsm` to the main runner and optional `--policies` selection to
the random-workload runner. Its default remains Baseline/V1/V2. The latter file
remains ignored by Git under the repository's existing `.gitignore`; its working
copy was updated, but the ignore rules and staging were not changed.

### Verification

All 28 new focused tests passed, including a check that FSM never calls the old
scores or beam planner, accurate slack, safe sub-20% departure, charging followed
by retry, quarter-second stepping, no double assignment, unique shared-pad slots,
future-reservation yielding, invalid battery exclusion, recovery and deterministic
replay. The older test files referred to by historical sections were absent in
this checkout and were not rerun. `git diff --check` passed.

Ran exactly one full FSM workload: seed 42, unchanged 100 simulated minutes,
642 requests, 18.159 seconds wall time. Outcomes: 205 on time, 0 late, 423 rejected,
0 expired, 12 pending and 2 in flight. No drones failed; longest observed physical
low-battery wait was 600 simulated seconds, and pad utilization was about 97.9%.
This is an observation, not a guaranteed wait bound.

The workload fingerprint matches the previously recorded seed-42 comparison.
Those earlier runs delivered 221 on time for V1 and 220 for V2; neither policy
was rerun in this validation. The FSM delivered fewer packages on this workload.
The result was retained without seed-specific tuning or any claim of throughput
superiority. Graphical rendering was not tested.

Report: `benchmark-20260914T213215806969Z.json` under this task's
`outputs/fsm-validation/` directory. Full decision serialization was disabled for
the workload run; the focused tests verify the FSM transition records themselves.
