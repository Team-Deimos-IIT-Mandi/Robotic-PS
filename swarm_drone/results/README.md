# Results

The old `logs/` directory (about 10 GB) was permanently deleted at the user's
request. Running simulation or workload commands that save full reports can
create it again. `benchmarks/` contains compact comparison summaries; those
summaries and the existing text and Markdown measurements are preserved.
Generated log and benchmark directories are ignored by Git.

`python3 -B scripts/analysis.py` reads the saved benchmark results only. It
does not run simulations, execute tests, or recreate the deleted logs.

## Files and folders

- `extreme_results.txt`: historical console output from an older baseline/V1/V2
  extreme comparison, including selected package traces. Its 58-request workload
  differs from the newer seed-42 benchmark; do not combine their denominators.
- `v3_workload_results.md`: recorded V3 before/after and hybrid-policy results
  for extreme seeds 42, 99, and 7 and a HARD workload, with charging metrics,
  policy details, and historical verification notes.
- [benchmarks/](benchmarks/README.md): small JSON comparison reports. Includes
  one full one-hour extreme run and one 12-second execution-path smoke run.
- `analysis.md`: optional output, created only if you run
  `python3 -B scripts/analysis.py --output results/analysis.md`.
- `logs/`: currently deleted. Simulator/HARD/random commands that save reports
  can recreate it; it is not required for analysis of the compact saved results.

## Reading the results

Outcome counts distinguish on-time delivery, late delivery, rejection, expiry,
and unfinished work at the simulation cutoff. Rejected/impossible requests
must not silently disappear from an all-request success denominator. Compare
algorithms on the same manifest, seed, and duration, and inspect charging and
failure metrics alongside throughput. Existing results are not new executions.

See [scripts](../scripts/README.md) for analysis commands and which runners
write full reports versus compact summaries.
