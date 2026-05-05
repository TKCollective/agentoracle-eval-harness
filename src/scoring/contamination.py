"""
Contamination delta — the headline metric Beenz asked for.

For the same dev set, compares:
  - AgentOracle accuracy (with retrieval)
  - Parametric baseline accuracy (LLM-only, no retrieval)

The DELTA is the value retrieval is providing. A small delta means the LLM
already "knew" most answers from training-time exposure (contamination risk).
A large delta means retrieval is doing real work.

Output:
  - per-label deltas
  - overall accuracy delta with 95% CI
  - claim-level breakdown: claims AO got right that parametric got wrong (and vice versa)
  - bootstrap-resampled CI for the delta itself
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

from src.scoring.averitec_score import LABELS


def _load(jsonl_path: Path) -> list[dict]:
    rows: list[dict] = []
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _by_claim_id(rows: list[dict]) -> dict[int, dict]:
    return {int(r["claim_id"]): r for r in rows}


def _correct(row: dict) -> bool:
    return row["predicted_label"] == row["gold_label"]


def contamination_delta(ao_path: Path, parametric_path: Path, n_bootstrap: int = 1000) -> dict:
    ao = _load(ao_path)
    par = _load(parametric_path)
    ao_by = _by_claim_id(ao)
    par_by = _by_claim_id(par)

    # Only compare claims present in BOTH runs
    common_ids = sorted(set(ao_by) & set(par_by))
    if not common_ids:
        raise RuntimeError("no overlapping claim_ids between runs")

    ao_correct = [_correct(ao_by[i]) for i in common_ids]
    par_correct = [_correct(par_by[i]) for i in common_ids]

    ao_acc = sum(ao_correct) / len(ao_correct)
    par_acc = sum(par_correct) / len(par_correct)
    delta = ao_acc - par_acc

    # Bootstrap CI on the delta
    rng = random.Random(42)
    n = len(common_ids)
    deltas: list[float] = []
    for _ in range(n_bootstrap):
        idx = [rng.randrange(n) for _ in range(n)]
        a = sum(ao_correct[i] for i in idx) / n
        p = sum(par_correct[i] for i in idx) / n
        deltas.append(a - p)
    deltas.sort()
    ci_lo = deltas[int(0.025 * n_bootstrap)]
    ci_hi = deltas[int(0.975 * n_bootstrap)]

    # 4-cell breakdown
    both_right = sum(1 for i in common_ids if _correct(ao_by[i]) and _correct(par_by[i]))
    ao_only_right = sum(1 for i in common_ids if _correct(ao_by[i]) and not _correct(par_by[i]))
    par_only_right = sum(1 for i in common_ids if _correct(par_by[i]) and not _correct(ao_by[i]))
    both_wrong = sum(1 for i in common_ids if not _correct(ao_by[i]) and not _correct(par_by[i]))

    # Per-label delta
    per_label_delta: dict[str, dict] = {}
    for label in LABELS:
        cids = [i for i in common_ids if ao_by[i]["gold_label"] == label]
        if not cids:
            continue
        ao_l = sum(_correct(ao_by[i]) for i in cids) / len(cids)
        par_l = sum(_correct(par_by[i]) for i in cids) / len(cids)
        per_label_delta[label] = {
            "support": len(cids),
            "ao_accuracy": ao_l,
            "parametric_accuracy": par_l,
            "delta": ao_l - par_l,
        }

    # Claims AO uniquely got right — these are the strongest evidence retrieval did real work
    retrieval_credit_claim_ids = sorted(
        i for i in common_ids if _correct(ao_by[i]) and not _correct(par_by[i])
    )
    contamination_suspect_claim_ids = sorted(
        i for i in common_ids if _correct(par_by[i]) and not _correct(ao_by[i])
    )

    return {
        "n_common_claims": len(common_ids),
        "agentoracle_accuracy": ao_acc,
        "parametric_accuracy": par_acc,
        "delta": delta,
        "delta_95ci": [ci_lo, ci_hi],
        "interpretation": _interpret(delta, ci_lo),
        "breakdown": {
            "both_right": both_right,
            "ao_only_right": ao_only_right,
            "parametric_only_right": par_only_right,
            "both_wrong": both_wrong,
        },
        "per_label_delta": per_label_delta,
        "retrieval_credit_claim_ids": retrieval_credit_claim_ids[:50],   # cap for readability
        "contamination_suspect_claim_ids": contamination_suspect_claim_ids[:50],
    }


def _interpret(delta: float, ci_lo: float) -> str:
    if ci_lo <= 0:
        return (
            "WEAK: 95% CI of delta crosses zero. Retrieval may not be providing "
            "statistically significant lift over parametric baseline. Either dataset "
            "is too small or contamination is high."
        )
    if delta >= 0.20:
        return (
            "STRONG: Retrieval adds >20pp accuracy. AgentOracle is doing real work; "
            "parametric knowledge alone is insufficient for these claims."
        )
    if delta >= 0.10:
        return (
            "MODERATE: Retrieval adds 10-20pp. Real contribution but watch for "
            "subset of claims where the LLM already knows the answer."
        )
    return (
        "MARGINAL: Retrieval adds <10pp. Possible contamination — many of these "
        "claims may be familiar to the LLM from pretraining. Disclose openly."
    )


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ao", required=True, help="path to AgentOracle predictions.jsonl")
    p.add_argument("--parametric", required=True, help="path to parametric predictions.jsonl")
    p.add_argument("--out", default=None)
    args = p.parse_args()
    summary = contamination_delta(Path(args.ao), Path(args.parametric))
    text = json.dumps(summary, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    sys.exit(_cli())
