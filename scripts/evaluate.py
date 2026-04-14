#!/usr/bin/env python3
"""MMA2A Benchmark Evaluator.

Reads experiment results from results/ and computes the metrics
reported in the paper:

  1. Task Completion Accuracy (TCA) — overall and per-category
  2. End-to-End Latency — mean, median, p95, per-category
  3. Bandwidth Overhead — request/response bytes comparison
  4. Routing Decision Analysis — native vs transcode percentages
  5. Statistical significance — paired t-test on matched tasks

Outputs:
  - Console summary
  - results/evaluation_<timestamp>.json (machine-readable)
  - LaTeX table fragments ready to paste into the paper

Usage:
    python scripts/evaluate.py                          # latest results
    python scripts/evaluate.py results/mma2a_*.json results/text-bn_*.json
    python scripts/evaluate.py --latex                   # emit LaTeX tables
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

# run_experiment saves: {mode}_{%Y%m%d_%H%M%S}_{run_id}.json
RESULT_FILE_RE = re.compile(r"^(mma2a|text-bn)_(\d{8}_\d{6})_([a-f0-9]{12})\.json$")


def find_latest_paired_result_files() -> list[Path]:
    """Prefer the newest mma2a + text-bn pair that share the same benchmark run_id."""
    if not RESULTS_DIR.exists():
        return []
    candidates = [
        p for p in RESULTS_DIR.rglob("*.json")
        if not p.name.startswith("evaluation_")
    ]
    by_run: dict[str, dict[str, Path]] = defaultdict(dict)
    for p in candidates:
        m = RESULT_FILE_RE.match(p.name)
        if not m:
            continue
        mode, ts, run_id = m.group(1), m.group(2), m.group(3)
        by_run[run_id][mode] = p
    paired: list[tuple[str, str, list[Path]]] = []
    for run_id, modes in by_run.items():
        if "mma2a" in modes and "text-bn" in modes:
            ts = RESULT_FILE_RE.match(modes["mma2a"].name).group(2)
            paired.append((ts, run_id, [modes["mma2a"], modes["text-bn"]]))
    if paired:
        paired.sort(key=lambda x: x[0], reverse=True)
        chosen = paired[0][2]
        print(f"  (using paired run {paired[0][1]} from {paired[0][0]})")
        return chosen

    # Fallback: newest mma2a + newest text-bn by modification time (different run_ids)
    mma2a = sorted(
        [p for p in candidates if p.name.startswith("mma2a_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    textbn = sorted(
        [p for p in candidates if p.name.startswith("text-bn_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if mma2a and textbn:
        print("  (fallback: latest mma2a + latest text-bn by file mtime — prefer one benchmark run)")
        return [mma2a[0], textbn[0]]
    return []


# ── Helpers ──────────────────────────────────────────────────────────────

def load_results(paths: list[Path]) -> dict[str, list[dict]]:
    """Load results grouped by mode."""
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        mode = data.get("mode", "unknown")
        by_mode[mode].extend(data.get("results", []))
    return dict(by_mode)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    d = k - f
    return s[f] + d * (s[c] - s[f])


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def paired_t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Simple paired t-test. Returns (t_statistic, p_value_approx).

    For a proper p-value, use scipy.stats.ttest_rel. This is a rough
    approximation sufficient for the paper draft.
    """
    if len(a) != len(b) or len(a) < 2:
        return 0.0, 1.0
    diffs = [ai - bi for ai, bi in zip(a, b)]
    d_mean = mean(diffs)
    d_std = stdev(diffs)
    if d_std == 0:
        return float("inf") if d_mean != 0 else 0.0, 0.0
    n = len(diffs)
    t = d_mean / (d_std / math.sqrt(n))
    # Rough two-tailed p-value using normal approximation (good enough for n>30)
    p = 2 * (1 - _norm_cdf(abs(t)))
    return round(t, 4), round(p, 6)


def _norm_cdf(x: float) -> float:
    """Approximation of the standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ── Metric Computation ───────────────────────────────────────────────────

def compute_accuracy(results: list[dict]) -> dict:
    """Compute Task Completion Accuracy (TCA)."""
    valid = [r for r in results if not r.get("error")]
    correct = sum(1 for r in valid if r.get("action_correct"))
    total = len(valid)

    by_category: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in valid:
        cat = r.get("category", "unknown")
        by_category[cat]["total"] += 1
        if r.get("action_correct"):
            by_category[cat]["correct"] += 1

    return {
        "overall": {
            "correct": correct,
            "total": total,
            "accuracy": round(correct / max(total, 1), 4),
        },
        "by_category": {
            cat: {
                **vals,
                "accuracy": round(vals["correct"] / max(vals["total"], 1), 4),
            }
            for cat, vals in sorted(by_category.items())
        },
    }


def compute_latency(results: list[dict]) -> dict:
    """Compute latency statistics."""
    valid = [r for r in results if not r.get("error")]
    latencies = [r["latency_seconds"] for r in valid]

    by_category: dict[str, list[float]] = defaultdict(list)
    for r in valid:
        by_category[r.get("category", "unknown")].append(r["latency_seconds"])

    return {
        "overall": {
            "mean": round(mean(latencies), 4),
            "median": round(median(latencies), 4),
            "stdev": round(stdev(latencies), 4),
            "p95": round(percentile(latencies, 95), 4),
            "min": round(min(latencies), 4) if latencies else 0,
            "max": round(max(latencies), 4) if latencies else 0,
            "n": len(latencies),
        },
        "by_category": {
            cat: {
                "mean": round(mean(lats), 4),
                "median": round(median(lats), 4),
                "stdev": round(stdev(lats), 4),
                "n": len(lats),
            }
            for cat, lats in sorted(by_category.items())
        },
    }


def compute_bandwidth(results: list[dict]) -> dict:
    """Compute bandwidth overhead statistics."""
    valid = [r for r in results if not r.get("error")]

    request_bytes = [r.get("request_bytes", 0) for r in valid]
    response_bytes = [r.get("response_bytes", 0) for r in valid]
    total_bytes = [r.get("total_bytes", 0) for r in valid]

    return {
        "request": {
            "mean": round(mean(request_bytes), 0),
            "total": sum(request_bytes),
        },
        "response": {
            "mean": round(mean(response_bytes), 0),
            "total": sum(response_bytes),
        },
        "total": {
            "mean": round(mean(total_bytes), 0),
            "total": sum(total_bytes),
        },
        "n": len(valid),
    }


def compute_routing_analysis(results: list[dict]) -> dict:
    """Analyze routing decisions (native vs transcode)."""
    valid = [r for r in results if not r.get("error")]

    native_count = 0
    transcode_count = 0
    by_modality: dict[str, dict] = defaultdict(lambda: {"native": 0, "transcode": 0})

    for r in valid:
        for decision in r.get("routing_decisions", []):
            action = decision.get("action", "unknown")
            modality = decision.get("part_modality", "unknown")
            if action == "native":
                native_count += 1
                by_modality[modality]["native"] += 1
            elif action == "transcode":
                transcode_count += 1
                by_modality[modality]["transcode"] += 1

    total = native_count + transcode_count
    return {
        "total_decisions": total,
        "native": native_count,
        "transcode": transcode_count,
        "native_pct": round(100 * native_count / max(total, 1), 1),
        "transcode_pct": round(100 * transcode_count / max(total, 1), 1),
        "by_modality": {
            mod: {
                **counts,
                "native_pct": round(100 * counts["native"] / max(counts["native"] + counts["transcode"], 1), 1),
            }
            for mod, counts in sorted(by_modality.items())
        },
    }


def compute_comparison(mma2a: list[dict], textbn: list[dict]) -> dict:
    """Compare MMA2A vs Text-BN on matched tasks."""
    # Index by task_id for paired comparison
    mma2a_by_id = {r["task_id"]: r for r in mma2a if not r.get("error")}
    textbn_by_id = {r["task_id"]: r for r in textbn if not r.get("error")}

    common_ids = sorted(set(mma2a_by_id.keys()) & set(textbn_by_id.keys()))

    if not common_ids:
        return {"paired_tasks": 0, "message": "No common tasks for comparison"}

    # Paired latency comparison
    mma2a_latencies = [mma2a_by_id[tid]["latency_seconds"] for tid in common_ids]
    textbn_latencies = [textbn_by_id[tid]["latency_seconds"] for tid in common_ids]

    t_stat, p_value = paired_t_test(textbn_latencies, mma2a_latencies)

    # Accuracy comparison
    mma2a_correct = sum(1 for tid in common_ids if mma2a_by_id[tid].get("action_correct"))
    textbn_correct = sum(1 for tid in common_ids if textbn_by_id[tid].get("action_correct"))

    # Bandwidth comparison
    mma2a_bytes = mean([mma2a_by_id[tid].get("total_bytes", 0) for tid in common_ids])
    textbn_bytes = mean([textbn_by_id[tid].get("total_bytes", 0) for tid in common_ids])

    latency_improvement = mean(textbn_latencies) - mean(mma2a_latencies)
    latency_improvement_pct = 100 * latency_improvement / mean(textbn_latencies) if mean(textbn_latencies) > 0 else 0

    return {
        "paired_tasks": len(common_ids),
        "latency": {
            "mma2a_mean": round(mean(mma2a_latencies), 4),
            "textbn_mean": round(mean(textbn_latencies), 4),
            "improvement_seconds": round(latency_improvement, 4),
            "improvement_pct": round(latency_improvement_pct, 1),
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant": p_value < 0.05,
        },
        "accuracy": {
            "mma2a": round(mma2a_correct / len(common_ids), 4),
            "textbn": round(textbn_correct / len(common_ids), 4),
            "mma2a_correct": mma2a_correct,
            "textbn_correct": textbn_correct,
        },
        "bandwidth": {
            "mma2a_mean_bytes": round(mma2a_bytes, 0),
            "textbn_mean_bytes": round(textbn_bytes, 0),
            "overhead_pct": round(100 * (mma2a_bytes - textbn_bytes) / max(textbn_bytes, 1), 1),
        },
    }


# ── Output Formatting ────────────────────────────────────────────────────

def print_summary(evaluation: dict):
    """Print human-readable summary."""
    print("\n" + "=" * 70)
    print("  MMA2A BENCHMARK EVALUATION")
    print("=" * 70)

    for mode in ["mma2a", "text-bn"]:
        metrics = evaluation.get(mode)
        if not metrics:
            continue

        acc = metrics["accuracy"]
        lat = metrics["latency"]

        print(f"\n  {'MMA2A (Native)' if mode == 'mma2a' else 'Text-BN (Baseline)'}")
        print(f"  {'─' * 40}")
        print(f"  TCA (overall):  {acc['overall']['accuracy']:.1%}  ({acc['overall']['correct']}/{acc['overall']['total']})")

        for cat, cat_acc in acc["by_category"].items():
            label = cat.replace("_", " ").title()
            print(f"    {label:30s} {cat_acc['accuracy']:.1%}  ({cat_acc['correct']}/{cat_acc['total']})")

        print(f"  Latency (mean): {lat['overall']['mean']:.3f}s  (median={lat['overall']['median']:.3f}s, p95={lat['overall']['p95']:.3f}s)")
        print(f"  Bandwidth:      {metrics['bandwidth']['total']['mean']/1024:.1f} KB avg per task")

        routing = metrics.get("routing")
        if routing and routing["total_decisions"] > 0:
            print(f"  Routing:        {routing['native_pct']:.0f}% native, {routing['transcode_pct']:.0f}% transcode")

    # Comparison
    comp = evaluation.get("comparison")
    if comp and comp.get("paired_tasks", 0) > 0:
        print(f"\n  HEAD-TO-HEAD COMPARISON (n={comp['paired_tasks']} paired tasks)")
        print(f"  {'─' * 40}")

        lat = comp["latency"]
        print(f"  Latency improvement: {lat['improvement_pct']:.1f}% faster with MMA2A")
        print(f"    MMA2A: {lat['mma2a_mean']:.3f}s vs Text-BN: {lat['textbn_mean']:.3f}s")
        sig = "YES (p<0.05)" if lat["significant"] else f"NO (p={lat['p_value']:.4f})"
        print(f"    Statistically significant: {sig}  (t={lat['t_statistic']:.2f})")

        acc = comp["accuracy"]
        print(f"  Accuracy: MMA2A={acc['mma2a']:.1%} vs Text-BN={acc['textbn']:.1%}")

        bw = comp["bandwidth"]
        print(f"  Bandwidth overhead: {bw['overhead_pct']:+.1f}% (MMA2A vs Text-BN)")

    print()


def generate_latex_table(evaluation: dict) -> str:
    """Generate LaTeX table for the paper (Table 2 format)."""
    lines = []
    lines.append("% Auto-generated by evaluate.py")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\caption{CrossModal-CS Benchmark Results}")
    lines.append("\\label{tab:results}")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("\\toprule")
    lines.append("\\textbf{Category} & \\multicolumn{2}{c}{\\textbf{TCA (\\%)}} & \\multicolumn{2}{c}{\\textbf{Latency (s)}} \\\\")
    lines.append("\\cmidrule(lr){2-3} \\cmidrule(lr){4-5}")
    lines.append(" & MMA2A & Text-BN & MMA2A & Text-BN \\\\")
    lines.append("\\midrule")

    categories = set()
    for mode in ["mma2a", "text-bn"]:
        if mode in evaluation:
            categories.update(evaluation[mode]["accuracy"]["by_category"].keys())

    for cat in sorted(categories):
        label = cat.replace("_", " ").title()
        mma2a_acc = evaluation.get("mma2a", {}).get("accuracy", {}).get("by_category", {}).get(cat, {}).get("accuracy", 0)
        textbn_acc = evaluation.get("text-bn", {}).get("accuracy", {}).get("by_category", {}).get(cat, {}).get("accuracy", 0)
        mma2a_lat = evaluation.get("mma2a", {}).get("latency", {}).get("by_category", {}).get(cat, {}).get("mean", 0)
        textbn_lat = evaluation.get("text-bn", {}).get("latency", {}).get("by_category", {}).get(cat, {}).get("mean", 0)
        lines.append(f"{label} & {100*mma2a_acc:.1f} & {100*textbn_acc:.1f} & {mma2a_lat:.2f} & {textbn_lat:.2f} \\\\")

    # Overall
    mma2a_overall_acc = evaluation.get("mma2a", {}).get("accuracy", {}).get("overall", {}).get("accuracy", 0)
    textbn_overall_acc = evaluation.get("text-bn", {}).get("accuracy", {}).get("overall", {}).get("accuracy", 0)
    mma2a_overall_lat = evaluation.get("mma2a", {}).get("latency", {}).get("overall", {}).get("mean", 0)
    textbn_overall_lat = evaluation.get("text-bn", {}).get("latency", {}).get("overall", {}).get("mean", 0)
    lines.append("\\midrule")
    lines.append(f"\\textbf{{Overall}} & \\textbf{{{100*mma2a_overall_acc:.1f}}} & {100*textbn_overall_acc:.1f} & \\textbf{{{mma2a_overall_lat:.2f}}} & {textbn_overall_lat:.2f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    return "\n".join(lines)


def generate_latex_bandwidth_table(evaluation: dict) -> str:
    """Generate LaTeX table for bandwidth comparison (Table 3 format)."""
    lines = []
    lines.append("% Auto-generated by evaluate.py")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\caption{Bandwidth Overhead Comparison}")
    lines.append("\\label{tab:bandwidth}")
    lines.append("\\begin{tabular}{lcc}")
    lines.append("\\toprule")
    lines.append("\\textbf{Metric} & \\textbf{MMA2A} & \\textbf{Text-BN} \\\\")
    lines.append("\\midrule")

    mma2a_bw = evaluation.get("mma2a", {}).get("bandwidth", {})
    textbn_bw = evaluation.get("text-bn", {}).get("bandwidth", {})

    mma2a_req = mma2a_bw.get("request", {}).get("mean", 0) / 1024
    textbn_req = textbn_bw.get("request", {}).get("mean", 0) / 1024
    mma2a_resp = mma2a_bw.get("response", {}).get("mean", 0) / 1024
    textbn_resp = textbn_bw.get("response", {}).get("mean", 0) / 1024

    lines.append(f"Avg Request Size (KB) & {mma2a_req:.1f} & {textbn_req:.1f} \\\\")
    lines.append(f"Avg Response Size (KB) & {mma2a_resp:.1f} & {textbn_resp:.1f} \\\\")
    lines.append(f"Avg Total (KB) & {mma2a_req+mma2a_resp:.1f} & {textbn_req+textbn_resp:.1f} \\\\")

    comp = evaluation.get("comparison", {}).get("bandwidth", {})
    if comp:
        lines.append(f"Overhead vs Text-BN & {comp.get('overhead_pct', 0):+.1f}\\% & --- \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MMA2A Benchmark Evaluator")
    parser.add_argument("files", nargs="*", help="Result JSON files (default: latest in results/)")
    parser.add_argument("--latex", action="store_true", help="Generate LaTeX tables")
    parser.add_argument("--output", type=str, help="Output evaluation JSON path")
    args = parser.parse_args()

    # Find result files
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        if not RESULTS_DIR.exists():
            print("No results/ directory found. Run the benchmark first:")
            print("  python scripts/run_experiment.py")
            sys.exit(1)
        paired = find_latest_paired_result_files()
        if paired:
            paths = paired
        else:
            paths = sorted(
                p for p in RESULTS_DIR.rglob("*.json")
                if not p.name.startswith("evaluation_")
            )
            if len(paths) > 2:
                print(
                    "  Warning: no mma2a+text-bn pair found by run_id; loading all result JSONs.",
                    "Pass explicit files for a clean comparison.",
                )

    if not paths:
        print("No result files found.")
        sys.exit(1)

    print(f"Loading {len(paths)} result file(s)...")
    by_mode = load_results(paths)

    # Compute metrics per mode
    evaluation = {}
    for mode, results in by_mode.items():
        print(f"  {mode}: {len(results)} tasks")
        evaluation[mode] = {
            "accuracy": compute_accuracy(results),
            "latency": compute_latency(results),
            "bandwidth": compute_bandwidth(results),
            "routing": compute_routing_analysis(results),
        }

    # Compute head-to-head if both modes present
    if "mma2a" in by_mode and "text-bn" in by_mode:
        evaluation["comparison"] = compute_comparison(by_mode["mma2a"], by_mode["text-bn"])

    # Print summary
    print_summary(evaluation)

    # LaTeX tables
    if args.latex:
        print("\n% ── LATEX TABLE: Results ──")
        print(generate_latex_table(evaluation))
        print("\n% ── LATEX TABLE: Bandwidth ──")
        print(generate_latex_bandwidth_table(evaluation))

    # Save evaluation
    output_path = args.output or str(
        RESULTS_DIR / f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(evaluation, f, indent=2)
    print(f"Evaluation saved to {output_path}")


if __name__ == "__main__":
    main()
