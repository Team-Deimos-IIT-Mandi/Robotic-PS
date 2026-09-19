import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT / "results" / "benchmarks"
    / "extreme-seed42-20260918T173420913327Z.json"
)
HISTORICAL_SOURCE = PROJECT_ROOT / "results" / "v3_workload_results.md"


def analyze_report(path):
    path = Path(path)
    with path.open(encoding="utf-8") as stream:
        report = json.load(stream)
    rows = []
    for name, metrics in report["algorithms"].items():
        outcomes = metrics["outcomes"]
        requests = sum(outcomes.values())
        on_time = outcomes.get("DELIVERED_ON_TIME", 0)
        delivered = on_time + outcomes.get("DELIVERED_LATE", 0)
        rows.append({
            "algorithm": name,
            "requests": requests,
            "on_time": on_time,
            "on_time_percent": 100 * on_time / requests if requests else 0,
            "unfinished": outcomes.get("PENDING", 0) + outcomes.get("ASSIGNED", 0),
            "rejected": outcomes.get("REJECTED", 0),
            "expired": outcomes.get("EXPIRED", 0),
            "late": outcomes.get("DELIVERED_LATE", 0),
            "energy": metrics["energy"],
            "energy_per_delivery": metrics["energy"] / delivered if delivered else None,
            "charge_wait": metrics["charge_wait_seconds"],
            "peak_queue": metrics["peak_charging_queue"],
            "failed_drones": metrics["failed_drones"],
        })
    lines = [
        "# Saved algorithm analysis",
        "",
        f"Source: `{path.name}`",
        f"Workload: {report['workload']}; seed: {report['seed']}; "
        f"duration: {report['duration_seconds']:g} simulated seconds.",
        "",
        "This analysis reads existing results only. It does not run simulations or tests.",
        "Percentages use all observed requests, including impossible requests.",
        "Energy is the simulator's cumulative battery depletion, not measured watt-hours.",
        "",
        "| Algorithm | On time | On-time % | Unfinished | Rejected | Expired | Late | Energy | Energy/delivery | Charge wait (s) | Peak queue | Failed drones |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        efficiency = row["energy_per_delivery"]
        efficiency_text = f"{efficiency:.2f}" if efficiency is not None else "N/A"
        lines.append(
            f"| {row['algorithm']} | {row['on_time']}/{row['requests']} | "
            f"{row['on_time_percent']:.1f} | {row['unfinished']} | {row['rejected']} | "
            f"{row['expired']} | {row['late']} | {row['energy']:.2f} | "
            f"{efficiency_text} | {row['charge_wait']:.2f} | "
            f"{row['peak_queue']} | {row['failed_drones']} |"
        )
    if rows:
        best_count = max(row["on_time"] for row in rows)
        leaders = ", ".join(row["algorithm"] for row in rows if row["on_time"] == best_count)
        lines.extend(["", f"Most on-time deliveries in this saved run: {leaders} ({best_count})."])
    lines.extend([
        "",
        "Lower total energy alone does not imply a better scheduler: an algorithm may simply deliver fewer packages.",
        "Unfinished packages are measured at the simulation cutoff, not necessarily failed deliveries.",
        "A single seed or short run does not establish an overall winner across workloads.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Analyze saved algorithm results without rerunning anything")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="Optionally save the analysis as Markdown")
    args = parser.parse_args()
    text = analyze_report(args.input)
    if args.input.resolve() == DEFAULT_INPUT.resolve():
        text += (
            "\n## Previously recorded V3 comparisons\n\n"
            "Source: `results/v3_workload_results.md`; these are historical measurements, not new runs.\n\n"
            "The seed-42 extreme workload had 36 requests, including two physically impossible requests. "
            "Baseline, V1, V2, and V3 delivered 14, 30, 32, and 34 on time, respectively. "
            "V3 delivered all 34 feasible requests, but its charging wait (6.3 s) was higher than V2's (1.5 s).\n\n"
            "Historical final V3 extreme results: seed 99 delivered 81/99 requests; "
            "seed 7 delivered 81/101. These denominators include impossible requests. "
            "The HARD workload delivered 360/360 for V3; the saved notes report 100% success for all four algorithms. "
            "All recorded final V3 runs had zero failed drones.\n"
        )
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
