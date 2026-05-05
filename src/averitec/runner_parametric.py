"""
Parametric-baseline runner — same as averitec.runner but uses
ParametricClient instead of AgentOracleClient.

Output: results/<run_id>/predictions.jsonl with predicted_label set
based on the LLM-only verdict. No sources column populated.

Usage:
    python -m src.averitec.runner_parametric --limit 20 --run-id parametric-smoke
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

from src.averitec.dataset_loader import AveritecClaim, load_dev, label_distribution
from src.averitec.runner import AO_TO_AVERITEC, predict
from src.clients.parametric_client import ParametricClient

logger = logging.getLogger("ao.averitec.parametric")


def run(
    limit: int | None,
    run_id: str,
    out_dir: Path,
    model: str = "meta-llama/llama-3.3-70b-instruct",
    local_dev_json: Path | None = None,
) -> dict:
    out = out_dir / run_id
    out.mkdir(parents=True, exist_ok=True)

    claims = load_dev(limit=limit, use_local_json=local_dev_json)
    logger.info("loaded %d claims; gold dist=%s", len(claims), label_distribution(claims))

    log_file = out / "raw_calls.jsonl"
    client = ParametricClient(model=model, log_file=log_file)

    preds_path = out / "predictions.jsonl"
    counts: dict[str, int] = {}
    failures = 0
    t_start = time.monotonic()

    with preds_path.open("w") as f:
        for i, claim in enumerate(claims, 1):
            row = predict(client, claim, run_id=run_id)
            row["mode"] = "parametric"
            row["model"] = model
            f.write(json.dumps(row) + "\n")
            counts[row["predicted_label"]] = counts.get(row["predicted_label"], 0) + 1
            if not row["ok"]:
                failures += 1
            if i % 25 == 0 or i == len(claims):
                logger.info("progress %d/%d (failures=%d)", i, len(claims), failures)

    elapsed = time.monotonic() - t_start
    manifest = {
        "run_id": run_id,
        "mode": "parametric",
        "model": model,
        "started_at": time.time() - elapsed,
        "elapsed_s": elapsed,
        "limit": limit,
        "n_claims": len(claims),
        "n_failures": failures,
        "label_distribution_gold": label_distribution(claims),
        "label_distribution_pred": counts,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("parametric run complete: %s", manifest)
    return manifest


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--run-id", default=f"parametric-{uuid.uuid4().hex[:8]}")
    p.add_argument("--out-dir", default="results")
    p.add_argument("--model", default="meta-llama/llama-3.3-70b-instruct")
    p.add_argument("--local-dev-json", default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(
        limit=args.limit,
        run_id=args.run_id,
        out_dir=Path(args.out_dir),
        model=args.model,
        local_dev_json=Path(args.local_dev_json) if args.local_dev_json else None,
    )


if __name__ == "__main__":
    sys.exit(_cli())
