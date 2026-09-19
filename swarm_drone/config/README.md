# Configuration and dependencies

## Files

- `requirements.txt`: Python package dependencies: `opencv-python` for the
  renderer and `numpy` for numerical/image operations. Versions are not pinned.

## Installation

From the repository root with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r config/requirements.txt
```

On Windows, use `python` instead of `python3`; PowerShell activation is
`.venv\Scripts\Activate.ps1`. Recreate the environment on each laptop rather
than copying `.venv`, which contains machine-specific interpreter paths.

Runtime flags are defined in the simulation/workload scripts, not in this
folder. Portable default output locations are in `swarm_drone/paths.py`.
The headless simulation still imports OpenCV; dependencies must be installed
even when no renderer window is opened.
