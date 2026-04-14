#!/usr/bin/env python3
"""McNemar's test and bootstrap 95% CI for paired MMA2A vs Text-BN accuracy.

Defaults point at the paper's paired run under results/run2-gemini-reasoning/.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2_contingency

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MMA2A = (
    PROJECT_ROOT
    / "results/run2-gemini-reasoning/mma2a_20260413_165258_afffb9b1bcf7.json"
)
DEFAULT_TEXT_BN = (
    PROJECT_ROOT
    / "results/run2-gemini-reasoning/text-bn_20260413_165923_afffb9b1bcf7.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mma2a",
        type=Path,
        default=DEFAULT_MMA2A,
        help="MMA2A pipeline result JSON",
    )
    parser.add_argument(
        "--text-bn",
        type=Path,
        default=DEFAULT_TEXT_BN,
        help="Text-BN pipeline result JSON",
    )
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=10_000,
        help="Bootstrap resamples for TCA difference CI",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    for label, path in ("MMA2A", args.mma2a), ("Text-BN", args.text_bn):
        if not path.is_file():
            print(f"Error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)

    print("Loading JSON files...")
    with open(args.mma2a) as f:
        mma2a_data = json.load(f)
    with open(args.text_bn) as f:
        text_bn_data = json.load(f)

    mma2a_results = mma2a_data["results"]
    text_bn_results = text_bn_data["results"]

    print(f"MMA2A: {len(mma2a_results)} tasks")
    print(f"Text-BN: {len(text_bn_results)} tasks")

    task_id_to_mma2a = {task["task_id"]: task["action_correct"] for task in mma2a_results}
    task_id_to_text_bn = {task["task_id"]: task["action_correct"] for task in text_bn_results}

    common_task_ids = sorted(set(task_id_to_mma2a.keys()) & set(task_id_to_text_bn.keys()))
    print(f"Matching tasks: {len(common_task_ids)}")

    mma2a_correct = np.array([task_id_to_mma2a[tid] for tid in common_task_ids], dtype=bool)
    text_bn_correct = np.array([task_id_to_text_bn[tid] for tid in common_task_ids], dtype=bool)

    mma2a_tca = np.mean(mma2a_correct)
    text_bn_tca = np.mean(text_bn_correct)
    tca_diff = mma2a_tca - text_bn_tca

    print("\nAccuracy Summary:")
    print(f"  MMA2A TCA: {mma2a_tca:.4f} ({np.sum(mma2a_correct)}/{len(common_task_ids)})")
    print(f"  Text-BN TCA: {text_bn_tca:.4f} ({np.sum(text_bn_correct)}/{len(common_task_ids)})")
    print(f"  TCA Difference: {tca_diff:.4f}")

    b = np.sum(mma2a_correct & ~text_bn_correct)
    c = np.sum(~mma2a_correct & text_bn_correct)

    contingency = np.array([[0, b], [c, 0]])
    chi2, p_value, _dof, _expected = chi2_contingency(contingency)

    print("\nMcNemar's Test:")
    print(f"  b (MMA2A correct, Text-BN wrong): {b}")
    print(f"  c (MMA2A wrong, Text-BN correct): {c}")
    print(f"  Chi-squared statistic: {chi2:.6f}")
    print(f"  p-value: {p_value:.6f}")

    print(f"\nBootstrap 95% CI on TCA Difference ({args.bootstrap} resamples):")
    np.random.seed(args.seed)
    paired_outcomes = np.column_stack([mma2a_correct, text_bn_correct])
    bootstrap_diffs = []
    for _ in range(args.bootstrap):
        indices = np.random.choice(len(paired_outcomes), size=len(paired_outcomes), replace=True)
        boot_mma2a = paired_outcomes[indices, 0].astype(float).mean()
        boot_text_bn = paired_outcomes[indices, 1].astype(float).mean()
        bootstrap_diffs.append(boot_mma2a - boot_text_bn)

    bootstrap_diffs = np.array(bootstrap_diffs)
    ci_lower = np.percentile(bootstrap_diffs, 2.5)
    ci_upper = np.percentile(bootstrap_diffs, 97.5)
    mean_diff = np.mean(bootstrap_diffs)

    print(f"  Mean difference: {mean_diff:.6f}")
    print(f"  95% CI lower (2.5th percentile): {ci_lower:.6f}")
    print(f"  95% CI upper (97.5th percentile): {ci_upper:.6f}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nMcNemar's Test: b = {b}, c = {c}, chi2 = {chi2:.6f}, p-value = {p_value:.6f}")
    print(
        f"\nBootstrap 95% CI (TCA_MMA2A - TCA_Text-BN): "
        f"[{ci_lower:.6f}, {ci_upper:.6f}]"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
