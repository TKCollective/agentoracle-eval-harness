# Results

> **Status (May 14, 2026): Code public, results pending full run.**
>
> The full FEVER 1.0 dev + AVeriTeC 2024 dev evaluation runs are scheduled
> for May 15-17, 2026. First numbers will land here by **May 17, 2026 EOD PT**.

## Why code is public before results

We chose to separate the two dates on purpose:

1. **Code-public (today, May 14):** Independent reviewers can clone, build, and
   inspect the entire evaluation pipeline before any AgentOracle-side numbers
   exist in this repo. This is the strongest form of pre-commitment to
   reproducibility — anyone can examine the runner, scoring, and dataset
   loaders without trusting our numbers first.

2. **Results-public (May 17):** Full FEVER 1.0 dev (19,998 claims) + AVeriTeC
   2024 dev (500 claims) numbers run inside the published Docker image with
   the locked seed (42), then written to this file with tables, 95%
   confidence intervals, per-verdict breakdowns, and recall@5 / recall@10
   on evidence retrieval.

## What's in the repo today

- `src/fever/` — FEVER 1.0 runner (`runner.py`) + dataset loader
- `src/averitec/` — AVeriTeC 2024 runner (`runner.py`), dataset loader, parametric baseline (`runner_parametric.py`)
- `src/scoring/` — FEVER score, AVeriTeC Hungarian METEOR / Ev2R, recall@k (with both strict-URL and domain-fallback variants), contamination delta scorer
- `src/clients/` — AgentOracle `/evaluate` client + parametric (no-retrieval) baseline client for the contamination test
- `docker/Dockerfile` — reproducible build with all dependencies locked
- `scripts/` — `download_fever.sh`, `download_averitec.sh`, `run_full_eval.sh`, `check_response_shape.py`
- `results/smoke/` — 4-claim smoke-test output, demonstrates the pipeline produces valid JSON output. Not a real eval. See `results/smoke/scores.json`.

## Calibration disclosures

Three things reviewers should know about how the numbers in RESULTS.md will be produced:

### 1. Recall@K is reported in BOTH variants

`src/scoring/recall_at_k.py` exposes two variants:

- **`recall_at_k_strict`** — full-URL exact match (path-normalized). Conservative. A wrong article on the right domain does NOT count as a hit. Denominator is `|norm_gold|`.
- **`recall_at_k_domain_fallback`** — lenient. If no full-URL hits, fall back to domain-only matching. Useful when reviewers want to credit "retrieved the right source, just not the exact gold article URL" — a common case on fact-check sites that publish many articles per topic (snopes, factcheck.org, politifact, etc.).

The key caveat: when domain-fallback fires, the denominator switches from `|norm_gold|` to `|dom_gold|`. If gold cites two URLs on the same domain, fallback can produce R@K = 1.0 where strict produces 0.5. RESULTS.md will publish **BOTH** numbers side-by-side along with the `strict_minus_lenient` delta and the `fallback_fires_pct` (the fraction of claims where domain-fallback actually fired). Readers can compute either and see the gap.

Per @beenz on the v0.2 review thread (2026-05-15) — single-value R@K hides which variant a reviewer is reading.

### 2. /evaluate response-shape is pinned before each run

`scripts/check_response_shape.py` posts a known-good probe to `/evaluate` at `AGENTORACLE_API_URL` before the full eval, verifies every field that `clients/agentoracle_client.py:_parse_response` reads still resolves under at least one of its documented shape paths (top-level OR `result.*` nested), captures the observed `X-AgentOracle-API-Version` header (or `body.metadata.api_version` fallback), and exits non-zero on drift. This prevents a server-side response-shape change between the harness ship date (2026-05-14) and the results-publish date (2026-05-17) from silently moving downstream scores. The observed API version is included in RESULTS.md when the numbers land.

### 3. AVeriTeC parametric-only baseline for contamination

The contamination control runs the same AVeriTeC dev claims through a no-retrieval pure-LLM path (`runner_parametric.py`) and computes the delta against the AgentOracle-with-retrieval run. RESULTS.md will publish the delta as `agentoracle_score - parametric_score` per metric, with positive values indicating that grounded retrieval moved the score above what the bare LLM produces from its training-data memorization alone.

## How to reproduce when results land

```bash
# 1. Clone
git clone https://github.com/TKCollective/agentoracle-eval-harness
cd agentoracle-eval-harness

# 2. Download datasets (FEVER + AVeriTeC dev)
bash scripts/download_fever.sh
bash scripts/download_averitec.sh

# 3. Build the Docker image
docker build -t agentoracle-eval -f docker/Dockerfile .

# 4. Run the full eval (locked seed 42)
docker run --rm \
  -v $(pwd)/results:/results \
  -e AGENTORACLE_API_KEY=$AGENTORACLE_API_KEY \
  agentoracle-eval \
  bash scripts/run_full_eval.sh

# 5. Compare against the numbers landing here May 17
diff results/run_<timestamp>/scores.json RESULTS.md
```

## Sprint plan status

| Day | Date | Milestone | Status |
|---|---|---|---|
| 0 | Apr 30 | Kickoff + research | ✅ shipped |
| 1-2 | May 1-2 | FEVER reproducer | ✅ shipped |
| 3-4 | May 3-4 | AVeriTeC runner | ✅ shipped |
| 5 | May 5 | Evaluation scoring | ✅ shipped |
| 6-7 | May 6-7 | Recall metrics | ✅ shipped |
| 8 | May 8 | Contamination test | ✅ shipped |
| 9-10 | May 9-10 | Docker build + seed | ⚠️ in progress |
| 11 | May 11 | Run full eval | ⏳ pushed to May 15-17 |
| 12 | May 12 | Results writeup | ⏳ pushed to May 17 |
| 13 | May 13 | External reproducibility | ⏳ pushed to May 17 |
| **14** | **May 14** | **Public ship** | **✅ THIS RELEASE** |

## Why the slip on days 9-13

Same reason the IETF Internet-Draft filing moved from May 28 to June 5-10:
the consumer-facing numbers in this harness will be referenced by every
downstream verifier looking at AgentOracle's calibration claims for years.
Rushing them to hit a May 11 internal milestone produces noisy headline
numbers without enough sample size or CI rigor to survive scrutiny.

The four-day push to May 17 is intentional and disclosed in advance — it is
not a missed deadline, it is the reverse: hitting May 14 with code public
on time, and using May 15-17 for the full eval run rather than rushing it
into a fake May 13 timestamp.

External communications during this window characterize the harness as:
"AgentOracle eval harness public May 14, full reproducible FEVER + AVeriTeC
dev-set numbers landing in RESULTS.md May 17."

## License

Code: MIT. Results data: CC-BY 4.0. Datasets follow upstream licenses
(FEVER: CC-BY-SA 3.0 + Wikipedia ToS; AVeriTeC: ODbL).
