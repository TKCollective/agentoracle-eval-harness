# 14-Day Eval Harness Sprint — Internal Plan

**Public commit:** May 14, 2026 (made publicly to @beenz on Apr 30, 2026 via Coinbase Developer Discord #x402 thread).

**Operating principle:** Each day produces a verifiable artifact. If a daily checkpoint slips, ship the next day's slice anyway and circle back. The April rule applies: anytime there's an issue, fix it — don't wait.

## Day 0 — Apr 30 (KICKOFF — TODAY)

**Status:** ✅ COMPLETE
- [x] Repo scaffold (`agentoracle-eval-harness/`)
- [x] AVeriTeC dataset access verified (HuggingFace `chenxwh/AVeriTeC` — knowledge store + dev set + test set all downloadable, CC-BY-SA 4.0)
- [x] FEVER 1.0 dataset access verified (Cambridge / Thorne et al. — public CC-BY-SA 3.0)
- [x] Docker spec locked (matches FEVER 2024 reference: AWS g5.2xlarge, A10G GPU, 32GB RAM)
- [x] Sprint plan published (this file)
- [x] README v0.1 written

## Day 1–2 — May 1–2 (FEVER REPRODUCER)

**Goal:** Reproduce our prior 93.9% / 78.4% numbers in a fully reproducible way.

- [ ] `src/fever/dataset_loader.py` — load FEVER 1.0 dev set (19,998 claims)
- [ ] `src/fever/oracle_runner.py` — oracle-evidence mode: feed gold evidence to /evaluate, measure label accuracy
- [ ] `src/fever/e2e_runner.py` — end-to-end mode: /evaluate retrieves on its own, measure FEVER score
- [ ] `src/clients/agentoracle_client.py` — HTTP client w/ retries, x402 payment handling, rate limiting
- [ ] **Checkpoint:** Run on 200-claim subset (FEVER-paper-dev-200) — get scores consistent with our prior 93.9% / 78.4% within ±2pp

## Day 3–4 — May 3–4 (AVERITEC RUNNER)

**Goal:** First clean AVeriTeC dev-set run.

- [ ] `scripts/download_averitec.sh` — pulls knowledge store from HuggingFace
- [ ] `src/averitec/dataset_loader.py` — load dev set + knowledge store
- [ ] `src/averitec/runner.py` — runs each claim through /evaluate, captures verdict + retrieved evidence
- [ ] Map AgentOracle's 4-source verdicts (ACT / VERIFY / REJECT / abstain) to AVeriTeC's 4 labels (SUPPORTED / REFUTED / NEI / CONFLICTING)
- [ ] **Checkpoint:** First raw AVeriTeC dev run completes; numbers logged (no scoring yet)

## Day 5 — May 5 (SCORING)

- [ ] `src/scoring/hu_meteor.py` — Hungarian METEOR for question-only and Q+A matching
- [ ] `src/scoring/ev2r.py` — Ev2R approximate-matching scorer (per FEVER 2024 spec)
- [ ] `src/scoring/averitec_score.py` — combined AVeriTeC score (verdict + evidence quality threshold @ 0.25)
- [ ] **Checkpoint:** Full AVeriTeC score reported on Day 3-4 run

## Day 6–7 — May 6–7 (RECALL METRICS)

**Goal:** Beenz's specific request — "surface recall@5 on dev alongside the headline numbers."

- [ ] `src/scoring/recall_at_k.py` — implement R@5, R@10 against gold evidence URLs from AVeriTeC
- [ ] FEVER recall: implement R@5 / R@10 against FEVER's wiki-page-id gold evidence
- [ ] Add per-claim breakdowns (which claims AgentOracle gets retrieval right but verdict wrong, and vice versa)
- [ ] **Checkpoint:** RESULTS draft has all 4 columns: label_acc / e2e_score / R@5 / R@10

## Day 8 — May 8 (CONTAMINATION TEST)

**Goal:** Quantify parametric-knowledge contamination risk Beenz flagged.

- [ ] Add `--no-retrieval` flag to runners — feeds claim only to LLM, no AgentOracle web retrieval
- [ ] Run parametric-only baseline on same dev sets
- [ ] Compute "knowledge gap" = AgentOracle score − parametric-only score (smaller gap = more contamination, less retrieval value)
- [ ] **Checkpoint:** Contamination delta reported in writeup

## Day 9–10 — May 9–10 (DOCKER + DETERMINISM)

- [ ] `docker/Dockerfile` — based on `Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)` per FEVER 2024 spec
- [ ] Pin all dependencies (Python, model weights, library versions)
- [ ] Add seeded run (`SEED=42` env var, deterministic across runs)
- [ ] Build + push to Docker Hub: `tkcollective/ao-eval:2026-05-09`
- [ ] **Checkpoint:** `docker pull && docker run` reproduces previous day's results within ±0.1pp on subset

## Day 11 — May 11 (FULL RUN)

- [ ] Full FEVER 1.0 dev-set run (19,998 claims)
- [ ] Full AVeriTeC dev-set run (~500 claims)
- [ ] Full parametric-only baselines for both
- [ ] All results land in `results/run_2026-05-11.json`
- [ ] **Estimated cost:** ~$40 USDC + ~$15 OpenRouter Llama grader

## Day 12 — May 12 (RESULTS WRITEUP)

- [ ] `RESULTS.md` with tables, confidence intervals, per-verdict breakdowns
- [ ] Update [agentoracle-receipt-spec](https://github.com/TKCollective/agentoracle-receipt-spec) main README's provisional banner: replace "provisional" with "v1.0 reproducible — see eval-harness repo"
- [ ] Draft public announcement post (LinkedIn / X / Discord) — restrained tone, "results are public, here's the link"

## Day 13 — May 13 (REPRODUCIBILITY TEST)

**Critical:** an external reviewer should be able to clone + run.

- [ ] Spin a clean AWS g5.2xlarge instance from scratch
- [ ] `git clone && docker run` — must produce results within ±0.5pp of Day 11 numbers
- [ ] Document any setup gotchas in `docs/REPRODUCIBILITY.md`
- [ ] **Checkpoint:** if reproducibility fails, FIX before public ship — better to slip 24h than ship a non-reproducible harness

## Day 14 — May 14 (PUBLIC SHIP)

- [ ] Repo goes public
- [ ] `RESULTS.md` finalized
- [ ] Spec repo's provisional banner downgraded
- [ ] Post in Coinbase Developer Discord #x402 thread tagging @beenz
- [ ] (Optional) Submit to FEVER 2026 leaderboard if shared task is open
- [ ] Update [Apr 29 breakthrough memo](../../agentoracle_apr29_breakthrough_summary.md) with sprint completion

---

## Risk register

| Risk | Mitigation |
|---|---|
| AgentOracle API slows under sustained load | Implement adaptive rate limiting, $40 USDC budget cap, retry-on-429 with backoff |
| FEVER number drifts > ±2pp | Investigate before ship; could indicate model regression or eval bug |
| AVeriTeC score < 25% | Disclose honestly; probably reflects retrieval-pipeline weakness on real-world claims, which is its own learning |
| LLM grader (Llama 3.3 70B) unavailable on OpenRouter | Fallback: Llama 3.3 70B via fireworks.ai or together.ai |
| Reproducibility fails on Day 13 | Cancel ship, fix, slip to May 16. Better to slip than ship broken |
| Contamination delta is large (e.g., AgentOracle barely beats parametric-only) | Disclose loudly; pivot narrative from "high accuracy" to "verifiable provenance + calibration" |

## What success looks like on May 14

- `RESULTS.md` shows 4 columns × 2 datasets: label_acc, e2e, R@5, R@10
- AVeriTeC dev score in **30-50% range** (target; below 25% is concerning, above 50% is suspect)
- Parametric-only baseline shows **meaningful gap** (>10pp under AgentOracle = retrieval is doing real work)
- One external person has cloned, run, and reproduced within ±0.5pp
- The provisional banner on the spec repo is gone

## What failure looks like

- The harness is published but slow (>1 min/claim) — fail efficiency criteria
- Numbers swing wildly between runs — non-deterministic, can't trust
- AVeriTeC score < 15% — barely beats baseline
- We can't reproduce on a clean instance — credibility-damaging

In any of these cases: ship the harness anyway with the bad numbers, write a "what we learned" postmortem, commit to v2. Honesty > optics.
