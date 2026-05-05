"""
FEVER runner — sends each FEVER dev-set claim through AgentOracle's
/evaluate endpoint and records predicted verdict, sources, latency.

Outputs:
  results/<run_id>/predictions.jsonl
  results/<run_id>/manifest.json

FEVER label mapping:
  AO "act"              -> "SUPPORTS"
  AO "verify"           -> "SUPPORTS"   (high-confidence-but-needs-secondary)
  AO "reject"           -> "REFUTES"
  AO "abstain"          -> "NOT ENOUGH INFO"

Usage:
    python -m src.fever.runner --limit 200 --run-id fever-paper-dev-200
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

from src.clients.agentoracle_client import AgentOracleClient
from src.fever.dataset_loader import FeverClaim, label_distribution, load_dev

logger = logging.getLogger("ao.fever.runner")


AO_TO_FEVER: dict[str, str] = {
    "act": "SUPPORTS",
    "verify": "SUPPORTS",
    "reject": "REFUTES",
    "abstain": "NOT ENOUGH INFO",
}


def predict(client, claim: FeverClaim, run_id: str) -> dict:
    t0 = time.monotonic()
    try:
        resp = client.evaluate(claim.claim, run_id=run_id)
        ok = True
        err = None
    except Exception as exc:  # noqa: BLE001
        return {
            "claim_id": claim.claim_id,
            "claim": claim.claim,
            "gold_label": claim.label,
            "predicted_label": "NOT ENOUGH INFO",
            "ao_verdict": None,
            "confidence": 0.0,
            "sources": [],
            "gold_pages": claim.gold_pages,
            "latency_s": time.monotonic() - t0,
            "ok": False,
            "error": str(exc),
        }
    pred = AO_TO_FEVER.get(resp.verdict.lower(), "NOT ENOUGH INFO")
    return {
        "claim_id": claim.claim_id,
        "claim": claim.claim,
        "gold_label": claim.label,
        "predicted_label": pred,
        "ao_verdict": resp.verdict,
        "confidence": resp.confidence,
        "sources": resp.sources,
        "gold_pages": claim.gold_pages,
        "latency_s": resp.latency_s,
        "evaluation_id": resp.evaluation_id,
        "ok": ok,
        "error": err,
    }


def run(
    limit: int | None,
    run_id: str,
    out_dir: Path,
    base_url: str = "https://agentoracle.co",
    local_jsonl: Path | None = None,
) -> dict:
    out = out_dir / run_id
    out.mkdir(parents=True, exist_ok=True)

    claims = load_dev(limit=limit, use_local_jsonl=local_jsonl)
    logger.info("loaded %d FEVER dev claims; gold dist=%s", len(claims), label_distribution(claims))

    log_file = out / "raw_calls.jsonl"
    client = AgentOracleClient(base_url=base_url, log_file=log_file)
    preds_path = out / "predictions.jsonl"
    counts: dict[str, int] = {}
    failures = 0
    t_start = time.monotonic()

    with preds_path.open("w") as f:
        for i, claim in enumerate(claims, 1):
            row = predict(client, claim, run_id=run_id)
            f.write(json.dumps(row) + "\n")
            counts[row["predicted_label"]] = counts.get(row["predicted_label"], 0) + 1
            if not row["ok"]:
                failures += 1
            if i % 50 == 0 or i == len(claims):
                logger.info("progress %d/%d (failures=%d)", i, len(claims), failures)

    elapsed = time.monotonic() - t_start
    manifest = {
        "run_id": run_id,
        "dataset": "fever-1.0-paper_dev",
        "started_at": time.time() - elapsed,
        "elapsed_s": elapsed,
        "base_url": base_url,
        "limit": limit,
        "n_claims": len(claims),
        "n_failures": failures,
        "label_distribution_gold": label_distribution(claims),
        "label_distribution_pred": counts,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("FEVER run complete: %s", manifest)
    return manifest


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--run-id", default=f"fever-{uuid.uuid4().hex[:8]}")
    p.add_argument("--out-dir", default="results")
    p.add_argument("--base-url", default="https://agentoracle.co")
    p.add_argument("--local-jsonl", default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(
        limit=args.limit,
        run_id=args.run_id,
        out_dir=Path(args.out_dir),
        base_url=args.base_url,
        local_jsonl=Path(args.local_jsonl) if args.local_jsonl else None,
    )


if __name__ == "__main__":
    sys.exit(_cli())
