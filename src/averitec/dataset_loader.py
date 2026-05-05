"""
AVeriTeC dataset loader.

Pulls the dev split from HuggingFace `chenxwh/AVeriTeC` (CC-BY-SA 4.0) and
returns a normalized list of claims with gold metadata.

Usage:
    from src.averitec.dataset_loader import load_dev
    claims = load_dev(limit=None)  # full dev set ~500 claims
    claims = load_dev(limit=20)    # smoke-test subset
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


# AVeriTeC's 4 verdict labels (FEVER 2024 spec)
VERDICTS = {"Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"}


@dataclass
class AveritecClaim:
    """One AVeriTeC dev/test instance."""

    claim_id: int
    claim: str                              # the natural-language claim
    label: str                              # gold verdict (one of VERDICTS)
    speaker: Optional[str] = None
    claim_date: Optional[str] = None
    reporting_source: Optional[str] = None
    location_iso_code: Optional[str] = None
    claim_types: list[str] = field(default_factory=list)
    fact_checking_strategies: list[str] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)   # gold Q+A evidence
    gold_urls: list[str] = field(default_factory=list)              # extracted from questions[].answers[].source_url

    def short(self) -> str:
        return f"#{self.claim_id} [{self.label}] {self.claim[:90]}"


def load_dev(
    cache_dir: Optional[str] = None,
    limit: Optional[int] = None,
    use_local_json: Optional[Path] = None,
) -> list[AveritecClaim]:
    """
    Load AVeriTeC dev split.

    Order of preference:
      1. `use_local_json` — if a local dev.json (or similar) is provided, parse it directly.
         This is the fastest path; produced by `scripts/download_averitec.sh`.
      2. HuggingFace `datasets` library — `chenxwh/AVeriTeC` repo, `dev` split.
    """
    raw: Iterable[dict[str, Any]]

    if use_local_json is not None:
        with Path(use_local_json).open() as f:
            raw = json.load(f)
    else:
        try:
            from datasets import load_dataset  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "datasets library not installed; either pip install datasets, "
                "or pass use_local_json=<path-to-dev.json>"
            ) from exc

        cache = cache_dir or os.environ.get("HF_DATASETS_CACHE") or "~/.cache/huggingface"
        ds = load_dataset("chenxwh/AVeriTeC", split="dev", cache_dir=os.path.expanduser(cache))
        raw = ds  # iterable of dicts

    claims: list[AveritecClaim] = []
    for i, row in enumerate(raw):
        if limit is not None and i >= limit:
            break
        questions = row.get("questions") or []
        gold_urls = []
        for q in questions:
            for a in q.get("answers") or []:
                src = a.get("source_url")
                if src:
                    gold_urls.append(src)
        claims.append(
            AveritecClaim(
                claim_id=int(row.get("claim_id", i)),
                claim=row["claim"],
                label=row["label"],
                speaker=row.get("speaker"),
                claim_date=row.get("claim_date"),
                reporting_source=row.get("reporting_source"),
                location_iso_code=row.get("location_iso_code"),
                claim_types=list(row.get("claim_types") or []),
                fact_checking_strategies=list(row.get("fact_checking_strategies") or []),
                questions=questions,
                gold_urls=gold_urls,
            )
        )
    return claims


def label_distribution(claims: list[AveritecClaim]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in claims:
        out[c.label] = out.get(c.label, 0) + 1
    return out
