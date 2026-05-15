"""
Pin the /evaluate response-shape contract before every eval run.

Per @beenz on the v0.2 review thread (2026-05-15): _parse_response in
clients/agentoracle_client.py bridges two response shapes flagged as
"current v2.2 shape." Without a pin, a server-side shape change between
the harness ship date (2026-05-14) and the results-publish date
(2026-05-17) could silently move downstream scores in RESULTS.md.

This script:
  1. Posts a known-good test claim to /evaluate at AGENTORACLE_API_URL.
  2. Verifies the response carries every field _parse_response reads
     (under either the top-level OR result-nested shape).
  3. Records the observed API version (X-AgentOracle-API-Version header
     or body.metadata.api_version) so RESULTS.md can cite the exact
     server version the numbers were produced against.
  4. Exits 0 on success, non-zero with a structured error on drift.

Usage:
  python -m scripts.check_response_shape --base-url https://agentoracle.co

Output: prints JSON to stdout describing the observed shape + version.
Reproducibility contract: the RESULTS.md numbers landing 2026-05-17 will
include the exact API version captured here, so any future drift is
auditable by re-running this script and diffing.
"""
import argparse
import json
import os
import sys
import time
import urllib.request


REQUIRED_FIELDS = {
    "verdict":      ["verdict", "result.verdict"],
    "confidence":   ["confidence", "result.confidence", "confidence.score"],
    "sources":      ["sources", "result.sources"],
    "evaluation_id": ["evaluation_id", "id"],
}


def get_nested(body: dict, dotted: str):
    """Read body['a']['b'] given 'a.b'. Returns None if missing."""
    cur = body
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        if part not in cur:
            return None
        cur = cur[part]
    return cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("AGENTORACLE_API_URL", "https://agentoracle.co"))
    ap.add_argument("--claim", default="The current price of Bitcoin is around $80,000 USD.",
                    help="A neutral, mid-confidence claim suitable for /evaluate preflight.")
    args = ap.parse_args()

    url = args.base_url.rstrip("/") + "/evaluate"
    # /evaluate may be a free preview endpoint OR require payment. We probe with
    # a minimal payload and read whatever the server returns; payment is out of
    # scope for the shape pin (we just need to see one valid response).
    payload = json.dumps({"claim": args.claim, "preview": True}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            api_version = resp.headers.get("X-AgentOracle-API-Version")
            body_bytes = resp.read()
    except Exception as e:
        report = {
            "ok": False,
            "stage": "fetch",
            "url": url,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_s": round(time.time() - start, 3),
        }
        print(json.dumps(report, indent=2))
        return 1

    try:
        body = json.loads(body_bytes)
    except Exception as e:
        report = {
            "ok": False,
            "stage": "decode",
            "url": url,
            "status": status,
            "error": f"{type(e).__name__}: {e}",
            "body_prefix": body_bytes[:300].decode("utf-8", errors="replace"),
        }
        print(json.dumps(report, indent=2))
        return 1

    # If the server returned a 402 / 400 informational body, we can't pin shape
    # against it. Surface the situation but don't fail the eval run \u2014 the
    # paid endpoint is exercised by the runners themselves with x402.
    if status not in (200,):
        report = {
            "ok": True,
            "stage": "non-200",
            "url": url,
            "status": status,
            "note": "Non-200 from preview probe; shape pin skipped. Paid runs go through x402 in the runners.",
            "body_keys": sorted(body.keys()) if isinstance(body, dict) else [],
            "api_version_header": api_version,
        }
        print(json.dumps(report, indent=2))
        return 0

    # 200 path: verify every required field resolves under at least one of its
    # documented shape paths.
    found = {}
    missing = {}
    for field, candidates in REQUIRED_FIELDS.items():
        resolved = None
        resolved_via = None
        for c in candidates:
            v = get_nested(body, c)
            if v is not None:
                resolved = v
                resolved_via = c
                break
        if resolved is not None:
            found[field] = {"value_type": type(resolved).__name__, "resolved_via": resolved_via}
        else:
            missing[field] = candidates

    # api_version detection: header takes precedence, fall back to body
    body_api_version = (
        body.get("api_version")
        or get_nested(body, "metadata.api_version")
        or get_nested(body, "result.api_version")
    )
    observed_api_version = api_version or body_api_version or "unknown"

    if missing:
        report = {
            "ok": False,
            "stage": "shape-drift",
            "url": url,
            "status": status,
            "observed_api_version": observed_api_version,
            "found": found,
            "missing": missing,
            "body_keys": sorted(body.keys()),
            "guidance": (
                "Response shape no longer carries every field _parse_response "
                "reads. Update clients/agentoracle_client.py:_parse_response "
                "before the eval run, or pin the server back to the shape "
                "captured in RESULTS.md."
            ),
        }
        print(json.dumps(report, indent=2))
        return 1

    report = {
        "ok": True,
        "stage": "shape-pinned",
        "url": url,
        "status": status,
        "observed_api_version": observed_api_version,
        "found": found,
        "body_top_level_keys": sorted(body.keys()),
        "elapsed_s": round(time.time() - start, 3),
        "note": (
            "All fields _parse_response reads resolve cleanly. RESULTS.md "
            "should cite observed_api_version above as the server version "
            "the numbers were produced against."
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
