"""
FEVER 1.0 dev set loader.

FEVER labels: SUPPORTS / REFUTES / NOT ENOUGH INFO

Source: Cambridge / Thorne et al. — public CC-BY-SA 3.0
HuggingFace: copenlu/fever or fever/fever (paper-dev split, 19998 claims)

Usage:
    from src.fever.dataset_loader import load_dev
    claims = load_dev(limit=200)   # paper-dev-200 subset for ±2pp checkpoint
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

VERDICTS = {"SUPPORTS", "REFUTES", "NOT ENOUGH INFO"}


@dataclass
class FeverClaim:
    claim_id: int
    claim: str
    label: str
    evidence: list[list[Any]] = field(default_factory=list)
    gold_pages: list[str] = field(default_factory=list)


def load_dev(
    limit: Optional[int] = None,
    use_local_jsonl: Optional[Path] = None,
    cache_dir: Optional[str] = None,
) -> list[FeverClaim]:
    raw: Iterable[dict[str, Any]]

    if use_local_jsonl is not None:
        rows: list[dict] = []
        with Path(use_local_jsonl).open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        raw = rows
    else:
        try:
            from datasets import load_dataset  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "datasets library not installed; pip install datasets, or pass use_local_jsonl=<path>"
            ) from exc
        ds = load_dataset("fever", "v1.0", split="paper_dev", cache_dir=cache_dir)
        raw = ds

    out: list[FeverClaim] = []
    for i, row in enumerate(raw):
        if limit is not None and i >= limit:
            break
        # FEVER evidence: list[list[ev_set]] where ev_set = [annotator_id, ev_id, wikipage, sent_id]
        evidence = row.get("evidence") or []
        # Flatten gold wiki page references for retrieval evaluation
        pages: list[str] = []
        for ev_set in evidence:
            for item in ev_set:
                if isinstance(item, list) and len(item) >= 3 and item[2]:
                    pages.append(str(item[2]))
        out.append(
            FeverClaim(
                claim_id=int(row.get("id", i)),
                claim=row["claim"],
                label=row["label"],
                evidence=evidence,
                gold_pages=list(set(pages)),
            )
        )
    return out


def label_distribution(claims: list[FeverClaim]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in claims:
        out[c.label] = out.get(c.label, 0) + 1
    return out
