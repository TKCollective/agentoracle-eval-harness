"""
AVeriTeC runner — sends each dev-set claim through AgentOracle's /evaluate
endpoint and collects (predicted verdict, confidence, retrieved sources,
latency, raw receipt JWS) into a JSONL run-log.

Outputs:
  results/<run_id>/predictions.jsonl   — one row per claim
  results/<run_id>/manifest.json       — run config + summary

Usage:
    python -m src.averitec.runner --limit 20 --run-id smoke
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from src.averitec.dataset_loader import AveritecClaim, load_dev, label_distribution
from src.clients.agentoracle_client import AgentOracleClient

logger = logging.getLogger("ao.averitec.runner")


# AgentOracle returns one of: "act" / "verify" / "reject" / "abstain"
# AVeriTeC labels: Supported / Refuted / Not Enough Evidence / Conflicting Evidence/Cherrypicking
# We map AO verdicts -> AVeriTeC labels; abstentions are kept distinct (NEI).
AO_TO_AVERITEC: dict[str, str] = {
    "act": "Supported",
    "verify": "Supported",   # AO's "verify" is high-confidence-but-needs-secondary; treat as supported
    "reject": "Refuted",
    "abstain": "Not Enough Evidence",
    "conflict": "Conflicting Evidence/Cherrypicking",
    "conflicting": "Conflicting Evidence/Cherrypicking",
}


def predict(client: AgentOracleClient, claim: AveritecClaim, run_id: str) -> dict:
    """Run a single claim through /evaluate and return a normalized prediction row."""
    t0 = time.monotonic()
    try:
        resp = client.evaluate(claim.claim, run_id=run_id)
        ok = True
        err = None
    except Exception as exc:  # noqa: BLE001
        ok = False
        err = str(exc)
        logger.warning("evaluate failed for claim_id=%s: %s", claim.claim_id, exc)
        return {
            "claim_id": claim.claim_id,
            "claim": claim.claim,
            "gold_label": claim.label,
            "predicted_label": "Not Enough Evidence",
            "ao_verdict": None,
            "confidence": 0.0,
            "sources": [],
            "gold_urls": claim.gold_urls,
            "latency_s": time.monotonic() - t0,
            "ok": ok,
            "error": err,
        }

    pred_label = AO_TO_AVERITEC.get(resp.verdict.lower(), "Not Enough Evidence")
    return {
        "claim_id": claim.claim_id,
        "claim": claim.claim,
        "gold_label": claim.label,
        "predicted_label": pred_label,
        "ao_verdict": resp.verdict,
        "confidence": resp.confidence,
        "sources": resp.sources,
        "gold_urls": claim.gold_urls,
        "latency_s": resp.latency_s,
        "evaluation_id": resp.evaluation_id,
        "ok": ok,
        "error": None,
    }


def run(
    limit: int | None,
    run_id: str,
    out_dir: Path,
    base_url: str = "https://agentoracle.co",
    local_dev_json: Path | None = None,
) -> dict:
    out = out_dir / run_id
    out.mkdir(parents=True, exist_ok=True)

    claims = load_dev(limit=limit, use_local_json=local_dev_json)
    logger.info(
        "loaded %d AVeriTeC dev claims; label dist=%s",
        len(claims),
        label_distribution(claims),
    )

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
            if i % 25 == 0 or i == len(claims):
                logger.info(
                    "progress %d/%d (failures=%d)", i, len(claims), failures
                )

    elapsed = time.monotonic() - t_start
    manifest = {
        "run_id": run_id,
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
    logger.info("run complete: %s", manifest)
    return manifest


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--run-id", default=f"run-{uuid.uuid4().hex[:8]}")
    p.add_argument("--out-dir", default="results")
    p.add_argument("--base-url", default="https://agentoracle.co")
    p.add_argument("--local-dev-json", default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(
        limit=args.limit,
        run_id=args.run_id,
        out_dir=Path(args.out_dir),
        base_url=args.base_url,
        local_dev_json=Path(args.local_dev_json) if args.local_dev_json else None,
    )


if __name__ == "__main__":
    sys.exit(_cli())
