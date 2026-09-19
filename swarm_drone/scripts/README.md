# Scripts

Run these scripts from the repository root. They resolve package/default output
paths relative to the repository, without a hardcoded user directory.
`__init__.py` also allows tests to import workload helpers through `scripts`.

## Saved-result analysis: no new simulation

`analysis.py` reads a compact benchmark JSON and prints a Markdown comparison
of on-time deliveries, unfinished/rejected/expired/late requests, energy,
energy per delivery, charging wait, queue peaks, and failed drones. Its default
input is the preserved 3,600-second extreme seed-42 report. For that default
report it also includes previously recorded V3 comparisons from the historical
measurements. It does not execute tests or import/run the simulator.

```sh
python3 -B scripts/analysis.py
python3 -B scripts/analysis.py --output results/analysis.md
python3 -B scripts/analysis.py --input results/benchmarks/another-report.json
```

Percentages in its main table use all observed requests, including impossible
ones. A low energy total may reflect fewer deliveries rather than efficiency.

## Workload runners: these run new simulations

- `run_v3_hard_visual.py`: visual V3 stress test with 30 initial requests,
  a request every five simulated seconds, and bursts of ten every minute
  (899 requests in the default 40 minutes). Uses heavy 1.5–2.5 kg payloads,
  45–120 second deadlines, and initial batteries of 32–50% to exercise
  charging. Destinations fit the visible map. Defaults to 5× playback.
  Configure pressure with `--initial-packages`, `--arrival-interval`,
  `--burst-size`, and `--burst-interval`; supports `--minutes`, `--seed`,
  `--time-scale`, `--headless`, and `--log-dir`. Reports keep the last five
  decisions per package to bound history growth during a busy run.
- `run_v3_visual.py`: opens the live OpenCV simulation with V3 selected,
  ten drones, and three charging pads. Defaults to 40 simulated minutes at
  5× speed (about eight real minutes). Displays movement, deliveries,
  batteries, and charging states. Press `Q` or `Esc` to stop early.
  Accepts the simulation CLI options, including `--minutes`, `--time-scale`,
  `--seed`, and `--log-dir`. Saves a decision report under `results/logs/`.
- `run_extreme_workload.py`: compares baseline, V1, V2, and V3 using identical
  seeded package manifests and wind. Extreme requests include an initial burst,
  later bursts/droughts/trickles, varied payloads, and varied deadlines. Its
  `--workload hard` mode creates one HARD request every ten seconds. Defaults
  to 60 simulated minutes, ten drones, and three pads. Prints outcome/charging
  metrics and optional traces; CLI saves compact JSON without package histories
  under `results/benchmarks/`. Helpers also support in-memory single-algorithm
  runs used by tests.
- `run_hard_workload.py`: older ten-minute comparison of baseline/V1/V2 with
  an initial five-package burst, regular HARD requests, and reduced batteries.
  Reports per-drone utilization, energy, charging waits, and pad utilization.
  Saves full package decision reports under `results/logs/`.
- `run_random_workload.py`: paired 100-minute random evaluations for
  baseline/V1/V2. Defaults to seeds 42, 100, and 2026; replays identical
  batteries/requests per seed and checks workload fingerprints. Tracks wait
  episodes, utilization, outcomes, means, and sample standard deviations.
  Saves a benchmark summary under `results/logs/`; also saves full decision
  reports unless `--no-decision-logs` is specified. Although CLI choices list
  `fsm`, the implementation currently rejects that policy; use baseline/V1/V2.

Examples for when you intentionally want new measurements:

```sh
python3 -B scripts/run_v3_visual.py
python3 -B scripts/run_v3_visual.py --minutes 1
python3 -B scripts/run_v3_hard_visual.py
python3 -B scripts/run_v3_hard_visual.py --minutes 1
python3 -B scripts/run_extreme_workload.py --seed 42 --no-traces
python3 -B scripts/run_extreme_workload.py --workload hard --no-traces
python3 -B scripts/run_random_workload.py --seeds 42 --no-decision-logs
python3 -B scripts/run_hard_workload.py
```

The old 10 GB logs were deleted. Runners that save full reports can recreate
`results/logs/`; `--no-decision-logs` suppresses random decision reports but
does not suppress its benchmark summary. Use `--log-dir` or `--output-dir`
where supported to select another destination. `-B` prevents `.pyc` caches.
