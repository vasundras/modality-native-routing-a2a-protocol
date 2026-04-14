#!/usr/bin/env python3
"""Generate LaTeX tables from evaluation results.

Convenience wrapper that loads the latest evaluation JSON and
outputs paper-ready LaTeX fragments.

Usage:
    python scripts/generate_tables.py
    python scripts/generate_tables.py results/evaluation_20260413_143000.json
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"


def find_latest_evaluation() -> Path:
    """Find the most recent evaluation JSON."""
    evals = sorted(RESULTS_DIR.glob("evaluation_*.json"))
    if not evals:
        print("No evaluation files found. Run evaluate.py first.")
        sys.exit(1)
    return evals[-1]


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = find_latest_evaluation()

    print(f"Loading: {path}")
    with open(path) as f:
        evaluation = json.load(f)

    # Import table generators from evaluate
    sys.path.insert(0, str(Path(__file__).parent))
    from evaluate import generate_latex_table, generate_latex_bandwidth_table

    print("\n% ════════════════════════════════════════")
    print("% Table 2: CrossModal-CS Benchmark Results")
    print("% ════════════════════════════════════════\n")
    print(generate_latex_table(evaluation))

    print("\n% ════════════════════════════════════════")
    print("% Table 3: Bandwidth Overhead Comparison")
    print("% ════════════════════════════════════════\n")
    print(generate_latex_bandwidth_table(evaluation))

    # Additional: per-category latency breakdown
    print("\n% ════════════════════════════════════════")
    print("% Table 4: Per-Category Latency Breakdown")
    print("% ════════════════════════════════════════\n")

    print("\\begin{table}[t]")
    print("\\centering")
    print("\\caption{Per-Category Latency Analysis}")
    print("\\label{tab:latency-detail}")
    print("\\begin{tabular}{lccccc}")
    print("\\toprule")
    print("\\textbf{Category} & \\textbf{Mode} & \\textbf{Mean (s)} & \\textbf{Median (s)} & \\textbf{Std Dev} & \\textbf{n} \\\\")
    print("\\midrule")

    categories = set()
    for mode in ["mma2a", "text-bn"]:
        if mode in evaluation:
            categories.update(evaluation[mode].get("latency", {}).get("by_category", {}).keys())

    for cat in sorted(categories):
        label = cat.replace("_", " ").title()
        for mode in ["mma2a", "text-bn"]:
            lat = evaluation.get(mode, {}).get("latency", {}).get("by_category", {}).get(cat, {})
            if lat:
                mode_label = "MMA2A" if mode == "mma2a" else "Text-BN"
                cat_label = label if mode == "mma2a" else ""
                print(f"{cat_label} & {mode_label} & {lat.get('mean', 0):.3f} & {lat.get('median', 0):.3f} & {lat.get('stdev', 0):.3f} & {lat.get('n', 0)} \\\\")
        print("\\addlinespace")

    print("\\bottomrule")
    print("\\end{tabular}")
    print("\\end{table}")

    # Routing decision breakdown
    print("\n% ════════════════════════════════════════")
    print("% Routing Decision Summary (for Section 5)")
    print("% ════════════════════════════════════════\n")

    for mode in ["mma2a", "text-bn"]:
        routing = evaluation.get(mode, {}).get("routing", {})
        if routing:
            print(f"% {mode}: {routing.get('native', 0)} native, {routing.get('transcode', 0)} transcode")
            print(f"%   = {routing.get('native_pct', 0):.0f}% native routing")
            for mod, counts in routing.get("by_modality", {}).items():
                print(f"%   {mod}: {counts.get('native', 0)} native, {counts.get('transcode', 0)} transcode ({counts.get('native_pct', 0):.0f}% native)")

    print("\nDone. Copy the LaTeX fragments above into your paper.")


if __name__ == "__main__":
    main()
