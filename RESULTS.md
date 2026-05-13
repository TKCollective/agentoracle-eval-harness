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

- `src/fever/` — FEVER 1.0 runner, oracle-evidence mode and end-to-end mode
- `src/averitec/` — AVeriTeC 2024 runner, dataset loader, parametric baseline
- `src/scoring/` — FEVER score, AVeriTeC Hungarian METEOR / Ev2R, recall@k,
  contamination delta scorer
- `src/clients/` — AgentOracle `/evaluate` client + parametric (no-retrieval)
  baseline client for the contamination test
- `docker/Dockerfile` — reproducible build with all dependencies locked
- `scripts/` — `download_fever.sh`, `download_averitec.sh`,
  `run_full_eval.sh`
- `results/smoke/` — 4-claim smoke-test output, demonstrates the pipeline
  produces valid JSON output. Not a real eval. See `results/smoke/scores.json`.

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
