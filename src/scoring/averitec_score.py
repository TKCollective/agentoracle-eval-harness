"""
AVeriTeC scoring pipeline.

Computes:
  - label_accuracy:     exact match on the 4 verdict labels
  - macro_F1 per label
  - confusion matrix
  - R@5, R@10 (via recall_at_k)
  - per-label and overall metrics, with 95% CI via bootstrap

Inputs:
  predictions.jsonl produced by averitec.runner.

Usage:
  python -m src.scoring.averitec_score --predictions results/<run_id>/predictions.jsonl \
      --out results/<run_id>/scores.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.scoring.recall_at_k import recall_at_k

LABELS = ["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]


def _load(jsonl_path: Path) -> list[dict]:
    rows: list[dict] = []
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def label_accuracy(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    correct = sum(1 for r in rows if r["predicted_label"] == r["gold_label"])
    return correct / len(rows)


def per_label_f1(rows: list[dict]) -> dict[str, dict]:
    by_label: dict[str, dict] = {}
    for label in LABELS:
        tp = sum(1 for r in rows if r["gold_label"] == label and r["predicted_label"] == label)
        fp = sum(1 for r in rows if r["gold_label"] != label and r["predicted_label"] == label)
        fn = sum(1 for r in rows if r["gold_label"] == label and r["predicted_label"] != label)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        support = sum(1 for r in rows if r["gold_label"] == label)
        by_label[label] = {"precision": prec, "recall": rec, "f1": f1, "support": support}
    return by_label


def macro_f1(per_label: dict[str, dict]) -> float:
    f1s = [v["f1"] for v in per_label.values() if v["support"] > 0]
    return sum(f1s) / len(f1s) if f1s else 0.0


def confusion_matrix(rows: list[dict]) -> dict[str, dict[str, int]]:
    cm: dict[str, dict[str, int]] = {g: {p: 0 for p in LABELS} for g in LABELS}
    for r in rows:
        g = r["gold_label"]
        p = r["predicted_label"]
        if g in cm and p in cm[g]:
            cm[g][p] += 1
    return cm


def macro_recall_k(rows: list[dict], k: int) -> float:
    scores = [recall_at_k(r.get("sources", []), r.get("gold_urls", []), k) for r in rows]
    return sum(scores) / len(scores) if scores else 0.0


def bootstrap_ci(values: list[float], n_iter: int = 1000, alpha: float = 0.05, seed: int = 42) -> tuple[float, float]:
    """95% CI for a mean via bootstrap."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(n_iter):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    lo = means[int((alpha / 2) * n_iter)]
    hi = means[int((1 - alpha / 2) * n_iter)]
    return lo, hi


def score_run(predictions_path: Path) -> dict:
    rows = _load(predictions_path)
    if not rows:
        raise RuntimeError(f"no rows in {predictions_path}")

    correct_indicators = [1.0 if r["predicted_label"] == r["gold_label"] else 0.0 for r in rows]
    r5_per = [recall_at_k(r.get("sources", []), r.get("gold_urls", []), 5) for r in rows]
    r10_per = [recall_at_k(r.get("sources", []), r.get("gold_urls", []), 10) for r in rows]

    summary = {
        "n_claims": len(rows),
        "label_accuracy": statistics.fmean(correct_indicators),
        "label_accuracy_95ci": bootstrap_ci(correct_indicators),
        "recall_at_5": statistics.fmean(r5_per),
        "recall_at_5_95ci": bootstrap_ci(r5_per),
        "recall_at_10": statistics.fmean(r10_per),
        "recall_at_10_95ci": bootstrap_ci(r10_per),
        "per_label_f1": per_label_f1(rows),
        "confusion_matrix": confusion_matrix(rows),
        "n_failures": sum(1 for r in rows if not r.get("ok", True)),
    }
    summary["macro_f1"] = macro_f1(summary["per_label_f1"])
    return summary


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    summary = score_run(Path(args.predictions))
    out_text = json.dumps(summary, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(out_text)
    print(out_text)


if __name__ == "__main__":
    sys.exit(_cli())
