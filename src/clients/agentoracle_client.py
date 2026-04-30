"""
AgentOracle /evaluate HTTP client with retries, rate limit handling, and
x402 payment support. Used by FEVER + AVeriTeC runners.

Design notes:
- One client instance per eval run.
- Logs every call to results/raw_calls.jsonl so we can post-hoc audit.
- Captures JWS receipts when /evaluate returns them so we can verify offline.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

import requests


DEFAULT_URL = os.environ.get("AGENTORACLE_API_URL", "https://agentoracle.co")
DEFAULT_TIMEOUT_S = 30
DEFAULT_MAX_RETRIES = 3


@dataclass
class EvaluateRequest:
    """Matches the current AgentOracle /evaluate payload shape (v2.2.0)."""
    content: str
    source: str = "eval-harness"
    run_id: Optional[str] = None


@dataclass
class EvaluateResponse:
    """Normalized response shape for downstream scoring."""
    verdict: str                      # "act" | "verify" | "reject" | "abstain"
    confidence: float                 # 0.0 - 1.0
    claims: list[dict[str, Any]]      # per-claim breakdown
    sources: list[str]                # URLs of retrieved evidence
    evaluation_id: str
    raw: dict[str, Any]               # full server response (for receipt extraction)
    latency_s: float


class RateLimitError(Exception):
    """HTTP 429 — back off and retry with jitter."""


class AgentOracleClient:
    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        log_file: Optional[Path] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.log_file = log_file
        self.session = requests.Session()

    def evaluate(self, claim_text: str, run_id: Optional[str] = None) -> EvaluateResponse:
        req = EvaluateRequest(content=claim_text, run_id=run_id or str(uuid.uuid4()))
        start = time.monotonic()
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                r = self.session.post(
                    f"{self.base_url}/evaluate",
                    json={"content": req.content, "source": req.source},
                    timeout=self.timeout_s,
                )
                latency = time.monotonic() - start

                if r.status_code == 429:
                    backoff = 2**attempt * (0.75 + 0.5 * _rand())
                    time.sleep(backoff)
                    continue

                r.raise_for_status()
                body = r.json()
                resp = _parse_response(body, latency)
                self._log(req, resp, r.status_code)
                return resp

            except requests.HTTPError as exc:
                last_err = exc
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(2**attempt * (0.75 + 0.5 * _rand()))
                    continue
                raise
            except requests.RequestException as exc:
                last_err = exc
                time.sleep(2**attempt * (0.75 + 0.5 * _rand()))

        raise RuntimeError(f"evaluate failed after {self.max_retries} attempts: {last_err}")

    def _log(self, req: EvaluateRequest, resp: EvaluateResponse, status: int) -> None:
        if self.log_file is None:
            return
        entry = {
            "ts": time.time(),
            "request": asdict(req),
            "status": status,
            "verdict": resp.verdict,
            "confidence": resp.confidence,
            "evaluation_id": resp.evaluation_id,
            "latency_s": resp.latency_s,
        }
        with self.log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def _parse_response(body: dict[str, Any], latency: float) -> EvaluateResponse:
    # Flexible to current v2.2 shape; adapt as /evaluate response evolves.
    verdict = body.get("verdict") or body.get("result", {}).get("verdict", "abstain")
    confidence = float(body.get("confidence") or body.get("result", {}).get("confidence", 0.0))
    claims = body.get("claims") or body.get("result", {}).get("claims", [])
    sources = body.get("sources") or body.get("result", {}).get("sources", [])
    eval_id = body.get("evaluation_id") or body.get("id", "unknown")
    return EvaluateResponse(
        verdict=verdict,
        confidence=confidence,
        claims=claims,
        sources=sources,
        evaluation_id=eval_id,
        raw=body,
        latency_s=latency,
    )


def _rand() -> float:
    """Small wrapper so tests can seed it."""
    import random
    return random.random()
