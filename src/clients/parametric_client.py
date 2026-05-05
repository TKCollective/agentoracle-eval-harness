"""
Parametric-only baseline client.

Day 8 of sprint plan — Beenz's contamination test. Sends each claim to a
plain LLM with NO retrieval, no AgentOracle, no web search. Measures how
much the LLM already "knows" the answer from training data alone.

Output: same EvaluateResponse shape as AgentOracleClient so runners can swap
client objects without code changes elsewhere.

LLM choice: Llama 3.3 70B Instruct via OpenRouter (matches our /evaluate's
verifier model, isolating the retrieval contribution).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import requests

from src.clients.agentoracle_client import EvaluateRequest, EvaluateResponse, _rand


PARAMETRIC_PROMPT = """You are a fact-checking system with NO access to retrieval, search, or external tools.
You must judge the claim using only your parametric (training-time) knowledge.

Claim: {claim}

Output a single JSON object on one line with these exact keys:
- verdict: one of "act" (claim is well-supported), "verify" (likely true but uncertain), "reject" (claim is false), or "abstain" (insufficient knowledge)
- confidence: float 0.0-1.0 reflecting your certainty
- rationale: 1-2 sentence explanation

Output ONLY the JSON object. Do not retrieve. Do not search. Use only what you remember."""


class ParametricClient:
    """LLM-only baseline. Same interface as AgentOracleClient.evaluate()."""

    def __init__(
        self,
        model: str = "meta-llama/llama-3.3-70b-instruct",
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_s: float = 30.0,
        max_retries: int = 3,
        log_file: Optional[Path] = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY required for parametric baseline")
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.log_file = log_file
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["HTTP-Referer"] = "https://agentoracle.co"
        self.session.headers["X-Title"] = "AgentOracle Eval Harness — parametric baseline"

    def evaluate(self, claim_text: str, run_id: Optional[str] = None) -> EvaluateResponse:
        req = EvaluateRequest(content=claim_text, source="parametric-baseline", run_id=run_id or str(uuid.uuid4()))
        start = time.monotonic()
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": PARAMETRIC_PROMPT.format(claim=claim_text)},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.0,  # deterministic; reproducibility > diversity
                    "response_format": {"type": "json_object"},
                    "seed": 42,
                }
                r = self.session.post(f"{self.base_url}/chat/completions", json=payload, timeout=self.timeout_s)
                latency = time.monotonic() - start

                if r.status_code == 429:
                    time.sleep(2**attempt * (0.75 + 0.5 * _rand()))
                    continue
                r.raise_for_status()
                body = r.json()
                content = body["choices"][0]["message"]["content"]
                parsed = _safe_json(content)
                resp = EvaluateResponse(
                    verdict=str(parsed.get("verdict", "abstain")).lower(),
                    confidence=_safe_float(parsed.get("confidence", 0.0)),
                    claims=[],          # parametric has no per-claim breakdown
                    sources=[],         # NO retrieval — this is the whole point
                    evaluation_id=body.get("id", "unknown"),
                    raw=body,
                    latency_s=latency,
                )
                self._log(req, resp, r.status_code)
                return resp
            except requests.HTTPError as exc:
                last_err = exc
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(2**attempt * (0.75 + 0.5 * _rand()))
                    continue
                raise
            except (requests.RequestException, KeyError, ValueError) as exc:
                last_err = exc
                time.sleep(2**attempt * (0.75 + 0.5 * _rand()))
        raise RuntimeError(f"parametric eval failed after {self.max_retries} attempts: {last_err}")

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
            "model": self.model,
        }
        with self.log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def _safe_json(content: str) -> dict[str, Any]:
    """LLM may wrap JSON in markdown fences; strip them."""
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1 :]
        if s.endswith("```"):
            s = s[: -3]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {"verdict": "abstain", "confidence": 0.0, "rationale": "json parse failed"}


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
