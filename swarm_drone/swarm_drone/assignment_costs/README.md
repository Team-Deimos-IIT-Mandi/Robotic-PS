# Assignment features and costs

These files turn physically feasible drone/package candidates into comparable
costs. They do not move drones, assign physical package ownership, or allocate
charging pads themselves. Lower scores are preferred, subject to each
scheduler's matching priorities.

## Files

- `__init__.py`: marks this folder as a Python subpackage.
- `features.py`: `calculate_assignment_features` estimates deadline slack,
  required energy relative to current battery, round-trip distance, accumulated
  flight time, and post-mission charging risk using the shared physics model.
- `baseline_cost.py`: `calculate_baseline_score` chooses the minimum-cost
  candidate supplied by the baseline scheduler and returns an explanation.
- `v1_cost.py`: `calculate_assignment_score` combines deadline, energy,
  normalized distance, utilization balance, and charging risk with weights
  10, 3, 1, 2, and 4. Returns the total and named cost components.
- `v2_cost.py`: `calculate_assignment_score_v2` keeps the deadline, energy,
  distance, and balance terms but sets the charging component to zero. V2
  deals with charging through its preparation and pad-allocation logic.

## How they are used

The scheduler filters candidates, extracts features, and normalizes distance
and utilization across the matrix before scoring. Baseline chooses candidates
package by package; V1/V2 pass them to the global matching optimizer.
Feasibility checks and optimizer priorities matter in addition to cost.

V3's predictive feature extraction and score are defined in
[`../assignment_algorithms/v3.py`](../assignment_algorithms/v3.py), not in
a separate cost file here. Its inputs include future availability and charging
forecasts; see the [algorithm README](../assignment_algorithms/README.md).
