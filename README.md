# AgentOracle Eval Harness

> **Status:** Sprint-in-progress. Started Apr 30, 2026. Target public ship: **May 14, 2026**.
>
> Committed to the [x402 Discord #verifiable-trust thread](https://discord.gg/cdp) on Apr 30, 2026 in response to [architectural review from @beenz](https://github.com/TKCollective/agentoracle-receipt-spec). This repo is the artifact that makes AgentOracle's calibration claims third-party reproducible.

## What this is

A reproducible evaluation harness that measures AgentOracle's [`/evaluate`](https://agentoracle.co/evaluate) endpoint against two public fact-verification benchmarks:

1. **FEVER 1.0 dev set** — the classic 19,998-claim benchmark (our headline number comes from here)
2. **AVeriTeC 2024 shared task** — the newer, contamination-controlled real-world benchmark

Both benchmarks report:
- **Label accuracy** (when oracle evidence is supplied)
- **End-to-end score** (retrieval pipeline + label — the "hard" setting)
- **Recall@5 / Recall@10** on evidence retrieval
- **Per-verdict breakdown** (SUPPORTED / REFUTED / NEI / CONFLICTING)

The entire eval runs inside a single Docker container on a reproducible AWS EC2 spec. Any third party can clone, `docker build && docker run`, and produce comparable numbers.

## Why this exists

Until this harness is public, AgentOracle's FEVER numbers are **provisional** — not third-party reproducible. That's disclosed in the [main receipt spec README](https://github.com/TKCollective/agentoracle-receipt-spec#readme). Shipping this harness moves the numbers from "provisional" to "reproducible."

See the [provisional disclosure banner](https://github.com/TKCollective/agentoracle-receipt-spec#readme) for the full explanation of why reproducibility matters for probabilistic-attestation primitives.

## Sprint plan (14 days)

| Day | Date | Milestone | Deliverable |
|---|---|---|---|
| 0 | Apr 30 | Kickoff + research | Repo scaffold, dataset access verified, Docker spec locked |
| 1–2 | May 1–2 | FEVER reproducer | FEVER dev-set runner, oracle-evidence mode, end-to-end mode |
| 3–4 | May 3–4 | AVeriTeC runner | AVeriTeC dev-set runner using the public knowledge store |
| 5 | May 5 | Evaluation scoring | Hungarian METEOR + Ev2R score integration |
| 6–7 | May 6–7 | Recall metrics | Recall@5 / Recall@10 on evidence retrieval |
| 8 | May 8 | Contamination test | Comparison: AgentOracle vs. "parametric knowledge only" (no web retrieval) baseline |
| 9–10 | May 9–10 | Docker build + seed | Deterministic run with fixed seed inside published Docker image |
| 11 | May 11 | Run full eval | End-to-end run on dev sets, results written to `/results` |
| 12 | May 12 | Results writeup | `RESULTS.md` with tables, CIs, per-verdict breakdowns |
| 13 | May 13 | External test | Independent clone + run on a clean EC2 instance to prove reproducibility |
| 14 | May 14 | **Public ship** | Repo goes public, announcement in x402 Discord, spec repo's provisional banner updated |

## Dataset licensing

- **FEVER 1.0**: Creative Commons Attribution-ShareAlike 3.0. Free to use for research + commercial. Citation: Thorne et al., 2018.
- **AVeriTeC**: CC-BY-SA 4.0 via [Huggingface chenxwh/AVeriTeC](https://huggingface.co/chenxwh/AVeriTeC). Knowledge store + dev set public. Test set hidden. Citation: Schlichtkrull et al., 2023/2024.

Both are peer-reviewed public benchmarks — no legal risk to running AgentOracle against them and publishing scores.

## Hardware target

Matching the FEVER 2024 shared task reference configuration so results are comparable to published systems:

| Component | Spec |
|---|---|
| Instance | AWS `g5.2xlarge` |
| GPU | Nvidia A10G, 23GB |
| CPU | 8 vCPUs |
| RAM | 32GB |
| Storage | 450GB (includes AVeriTeC knowledge store) |

AgentOracle is a **hosted API** — we don't run models locally. The harness runs HTTP calls to `https://agentoracle.co/evaluate`, so compute requirements are modest: the GPU is only used for the evaluation grader (Llama 3.3 70B or equivalent open-weights model per FEVER 2024 rules). In production runs we substitute an OpenRouter-hosted Llama 3.3 70B inference call to avoid local GPU requirements; this is disclosed in the RESULTS writeup.

## Repo structure

```
.
├── src/                 # eval runners + scoring
│   ├── fever/           # FEVER 1.0 dev-set runner
│   ├── averitec/        # AVeriTeC dev-set runner
│   ├── scoring/         # Hungarian METEOR, Ev2R, recall@k
│   └── clients/         # AgentOracle /evaluate + /research HTTP clients
├── scripts/             # setup, download, run
│   ├── download_fever.sh
│   ├── download_averitec.sh
│   └── run_full_eval.sh
├── docker/              # Dockerfile + build artifacts
├── results/             # published run outputs (gitignored raw; committed summaries)
└── docs/                # methodology, known limitations, FAQ
```

## Running the eval

```bash
# 1. Clone + build
git clone https://github.com/TKCollective/agentoracle-eval-harness
cd agentoracle-eval-harness
docker build -f docker/Dockerfile -t ao-eval .

# 2. Download datasets
./scripts/download_fever.sh       # ~45MB
./scripts/download_averitec.sh    # ~12GB (knowledge store)

# 3. Set API keys
export AGENTORACLE_API_URL=https://agentoracle.co
export OPENROUTER_API_KEY=...     # for Llama grader
export BASE_WALLET_PRIVATE_KEY=... # for x402 payments, ~$40 in USDC

# 4. Run
docker run -it --gpus all \
  -v $(pwd)/results:/results \
  -v $(pwd)/data:/data \
  -e OPENROUTER_API_KEY \
  ao-eval \
  ./scripts/run_full_eval.sh
```

Results land in `./results/run_<timestamp>.json` and `./results/RESULTS.md`.

## What's published

After the sprint completes:

1. **`RESULTS.md`** — tables with CI, side-by-side FEVER vs AVeriTeC
2. **`results/run_YYYY-MM-DD.json`** — raw scores + per-claim predictions
3. **Published Docker image** on Docker Hub: `tkcollective/ao-eval:YYYY-MM-DD`
4. **Signed receipt** — the evaluation run itself emits a signed receipt with a new `calibration.valid_until` anchor, logged back to the [main receipt spec repo](https://github.com/TKCollective/agentoracle-receipt-spec)

## Limitations (known today)

- **AVeriTeC test set is hidden.** We report dev-set scores only; test-set scores require submission to the FEVER workshop leaderboard
- **LLM contamination risk remains.** FEVER 1.0 corpus was public in 2018; modern LLMs may have parametric knowledge of specific claims. We include a "parametric-only" baseline (no web retrieval) to quantify this
- **Cost.** A full dev-set run costs ~$40 in x402 USDC payments to AgentOracle + ~$15 in OpenRouter Llama-grader calls. Budgeted, reproducible, disclosed
- **Not SOTA.** AgentOracle is a trust primitive, not a claim-verification benchmark maximizer. Our target is 30-50% AVeriTeC score, not the 63% high-water mark. We're calibrated, not tuned

## Questions

Open an issue here, or join the [Coinbase Developer Discord #x402 thread](https://discord.gg/cdp).

---

**License:** MIT (harness code). Dataset licenses per their respective owners.

**Cite this harness:**

```
@software{agentoracle_eval_2026,
  author  = {AgentOracle (TK Collective LLC)},
  title   = {AgentOracle Eval Harness: Reproducible benchmarking for probabilistic verification primitives},
  year    = {2026},
  url     = {https://github.com/TKCollective/agentoracle-eval-harness}
}
```
