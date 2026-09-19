# Drone Fleet Simulator

Run commands from the repository root. Python 3.10 or newer is required.
The `-B` flag prevents Python from generating `.pyc` cache files.

## Repository layout

```text
swarm_drone/
  assignment.py              Shared scheduling entry point
  assignment_algorithms/     Baseline, V1, V2, V3, and shared helpers
  assignment_costs/          Features and scoring
  simulation.py             Simulation loop and command-line interface
  drone_sim.py              State models and OpenCV renderer
  physics.py                Movement, energy, speed, and unit conversions
  charging.py               Charging infrastructure used by V2
  fsm.py                    Physical mission transitions
  telemetry.py              Mission safety checks
  wind.py                   Wind model
  paths.py                  Default output locations
scripts/                    Workload runners and saved-result analysis
tests/                      Current tests and shock trace script
  legacy/                   Historical FSM API tests
results/
  logs/                     Generated simulation reports (old 10 GB logs removed)
  benchmarks/               New workload comparison reports
docs/                       Historical README and change notes
config/requirements.txt     Python dependencies
```

Each project folder has its own file guide:

- [Simulator package](swarm_drone/README.md)
- [Assignment algorithms](swarm_drone/assignment_algorithms/README.md)
- [Assignment costs](swarm_drone/assignment_costs/README.md)
- [Scripts](scripts/README.md)
- [Tests](tests/README.md) and [legacy tests](tests/legacy/README.md)
- [Dependencies/configuration](config/README.md)
- [Historical documentation](docs/README.md)
- [Results](results/README.md) and [benchmark reports](results/benchmarks/README.md)
- [Local VS Code settings](.vscode/README.md)

## Install

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
```

On another laptop, recreate `.venv` locally rather than copying the existing
environment. On Windows, use `python` instead of `python3` and activate with
`.venv\Scripts\Activate.ps1` in PowerShell rather than `source`.
Source and default output paths are resolved relative to this repository,
not a particular user's home directory. VS Code search paths use
`${workspaceFolder}`; select the local Python interpreter in VS Code.

## Run

The default command opens the simulation window and plays **40 simulated
minutes in about 8 real minutes** at **5× speed**. The window shows the
simulated time and playback speed. Press `Q` or `Esc` to stop early.
Use `--time-scale` to change the playback speed; `--headless` runs without
the window or playback delays.

```sh
python3 -B -m swarm_drone.simulation
python3 -B scripts/run_v3_visual.py
python3 -B scripts/run_v3_hard_visual.py
python3 -B -m swarm_drone.simulation --headless --minutes 1 --algorithm v2
python3 -B scripts/run_extreme_workload.py --seed 42 --no-traces
python3 -B scripts/run_extreme_workload.py --workload hard --no-traces
python3 -B scripts/run_random_workload.py --seeds 42 --no-decision-logs
python3 -B scripts/run_hard_workload.py
```

Analyze the existing saved results without running simulations or tests:

```sh
python3 -B scripts/analysis.py
python3 -B scripts/analysis.py --output results/analysis.md
```

Use `--input path/to/report.json` to analyze another compact benchmark report.
The analysis script never reads or creates full simulation logs.

The V3 visual tester opens the same window with V3 selected, ten drones, and
three charging pads. It uses 5× playback by default. For a shorter visual test,
run `python3 -B scripts/run_v3_visual.py --minutes 1` (about 12 real seconds).
The window identifies the algorithm and shows drone movement, battery levels,
delivery requests, and charging states. Reports are saved when the run ends.

For a busy V3 stress test, run `python3 -B scripts/run_v3_hard_visual.py`.
It starts with 30 packages, adds one every five simulated seconds, and injects
bursts of ten every simulated minute: 899 requests over 40 minutes. Drones
start at 32–50% battery, with heavy payloads and 45–120 second deadlines.
Destinations stay on the visible map. The panel shows received requests,
outcomes, airborne drones, charging drones, and the charging queue.
Routes show current drone targets; completed/rejected/expired markers clear
from the map. Playback defaults to 5× (about eight real minutes).
At 5×, a one-minute preview takes about 12 real seconds. The panel shows
real elapsed time and measured average speed; the final `Timing:` line and
JSON report record actual speed separately from the requested speed.
Playback draws between catch-up steps at up to 30 frames per second.
Use `--minutes 1` for a short preview, or `--initial-packages 50 --burst-size 20`
for more pressure. Reports retain the last five decisions per package.

The extreme runner and simulation CLI support baseline, V1, V2, and V3.
You can also select V3 with `python3 -B -m swarm_drone.simulation --algorithm v3`.
The older HARD/random runners currently expose baseline, V1, and V2.
Default reports go to `results/logs/` or `results/benchmarks/`, even when a
script is launched from another working directory. Explicit output directory
options still override these defaults.

Import simulator code with `from swarm_drone import simulation, assignment`.
The scheduling entry point remains
`assignment.schedule_packages(drones, packages, time, pads, algorithm)`.

## Tests

```sh
python3 -B -m unittest discover -s tests -p 'test_assignment_modules.py'
python3 -B -m unittest discover -s tests -p 'test_assignment_v3.py'
python3 -B -m unittest discover -s tests -p 'test_edge_cases*.py'
python3 -B -m unittest discover -s tests -p 'test_invariants.py'
python3 -B tests/test_simulation.py
python3 -B tests/test_shock_log.py
```

Discovery also includes `tests/legacy/`. Those 28 historical tests still call
removed APIs such as `simulation.assign_packages_fsm`, so they currently error.
They are retained for reference; repository reorganization does not repair or
hide those failures. Use `test_assignment_modules.py` and `test_assignment_v3.py`
as discovery patterns to run the current assignment tests separately.

The preserved [historical README](docs/legacy_readme.md) and
[change notes](docs/changes.md) describe earlier implementations; their old
commands and feature claims may no longer apply. Previous V3 measurements are
in [results/v3_workload_results.md](results/v3_workload_results.md).
