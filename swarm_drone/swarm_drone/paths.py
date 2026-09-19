from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_LOG_DIR = RESULTS_DIR / "logs"
DEFAULT_BENCHMARK_DIR = RESULTS_DIR / "benchmarks"
