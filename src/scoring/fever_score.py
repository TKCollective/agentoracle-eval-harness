"""
FEVER scoring.

Reproduces:
  - Label accuracy (3-way: SUPPORTS / REFUTES / NOT ENOUGH INFO)
  - FEVER score (label_accuracy AND retrieved-evidence-correct-pages)
  - Per-label P/R/F1
  - Recall@K against gold wiki pages
  - 95% CI via bootstrap

Targets (our prior numbers): label_acc 93.9%, e2e FEVER score 78.4% on
paper_dev-200. ±2pp tolerance for reproduction.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

LABELS = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]


def _load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm_page_from_url(url: str) -> str:
    """FEVER gold pages are wiki page IDs (e.g., 'Barack_Obama'). AO returns
    URLs. Map URL → wiki page ID via en.wikipedia.org/wiki/<page> heuristic."""
    if not url:
        return ""
    u = url.lower()
    if "wikipedia.org/wiki/" in u:
        page = url.split("/wiki/", 1)[1]
        page = page.split("#", 1)[0].split("?", 1)[0]
        return page.replace(" ", "_")
    return ""


def evidence_match(retrieved: list[str], gold_pages: list[str], k: int = 5) -> bool:
    """FEVER e2e scoring: at least one gold page must appear in top-K retrieved sources."""
    if not gold_pages:
        # NEI claims have no gold evidence — treat as automatic match if retrieved is small
        return True
    norm_top = {_norm_page_from_url(u) for u in retrieved[:k] if u}
    return any(p.lower() in {n.lower() for n in norm_top} for p in gold_pages)


def label_accuracy(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r["predicted_label"] == r["gold_label"]) / len(rows)


def fever_score(rows: list[dict], k: int = 5) -> float:
    """FEVER score = label correct AND (NEI OR gold-page in top-K retrieved)."""
    if not rows:
        return 0.0
    hits = 0
    for r in rows:
        if r["predicted_label"] != r["gold_label"]:
            continue
        if r["gold_label"] == "NOT ENOUGH INFO":
            hits += 1
        elif evidence_match(r.get("sources", []), r.get("gold_pages", []), k=k):
            hits += 1
    return hits / len(rows)


def per_label_f1(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for label in LABELS:
        tp = sum(1 for r in rows if r["gold_label"] == label and r["predicted_label"] == label)
        fp = sum(1 for r in rows if r["gold_label"] != label and r["predicted_label"] == label)
        fn = sum(1 for r in rows if r["gold_label"] == label and r["predicted_label"] != label)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        out[label] = {
            "precision": prec, "recall": rec, "f1": f1,
            "support": sum(1 for r in rows if r["gold_label"] == label),
        }
    return out


def bootstrap_ci(values: list[float], n_iter: int = 1000, seed: int = 42) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_iter):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    return means[int(0.025 * n_iter)], means[int(0.975 * n_iter)]


def score_run(predictions_path: Path) -> dict:
    rows = _load(predictions_path)
    if not rows:
        raise RuntimeError(f"no rows in {predictions_path}")

    label_correct = [1.0 if r["predicted_label"] == r["gold_label"] else 0.0 for r in rows]
    e2e_correct = []
    for r in rows:
        ok_label = r["predicted_label"] == r["gold_label"]
        ok_evidence = (
            r["gold_label"] == "NOT ENOUGH INFO"
            or evidence_match(r.get("sources", []), r.get("gold_pages", []), k=5)
        )
        e2e_correct.append(1.0 if ok_label and ok_evidence else 0.0)

    return {
        "n_claims": len(rows),
        "label_accuracy": statistics.fmean(label_correct),
        "label_accuracy_95ci": bootstrap_ci(label_correct),
        "fever_score": statistics.fmean(e2e_correct),
        "fever_score_95ci": bootstrap_ci(e2e_correct),
        "per_label_f1": per_label_f1(rows),
        "n_failures": sum(1 for r in rows if not r.get("ok", True)),
        "targets": {"prior_label_accuracy": 0.939, "prior_fever_score": 0.784, "tolerance_pp": 0.02},
    }


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    summary = score_run(Path(args.predictions))
    text = json.dumps(summary, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    sys.exit(_cli())
