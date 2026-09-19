"""Visual V3 tester: 40 simulated minutes in about 8 real minutes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_drone.simulation import main


if __name__ == "__main__":
    main(default_algorithm="v3")
