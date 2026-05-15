#!/usr/bin/env bash
# Runs the full eval: FEVER + AVeriTeC + parametric-only baseline.
# Writes results to /results/<run-id>/...
#
# Calls the actual modules and their real arg surface. Verified against
# argparse declarations in:
#   src/fever/runner.py        (--limit, --run-id, --out-dir, --base-url, --local-jsonl)
#   src/averitec/runner.py     (--limit, --run-id, --out-dir, --base-url, --local-dev-json)
#   src/averitec/runner_parametric.py (--limit, --run-id, --out-dir, --model, --local-dev-json)
#   src/scoring/{fever_score,averitec_score,recall_at_k,contamination}.py
#
# Reproducibility contract:
#   - SEED is fixed for any in-runner sampling (passed via env, default 42)
#   - --base-url pins to https://agentoracle.co unless overridden
#   - All output paths are under /results/ inside the docker container
set -euo pipefail

TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
RUN_ID="full-${TS}"
OUT_DIR="/results/${RUN_ID}"
LOG_FILE="${OUT_DIR}/run.log"

mkdir -p "${OUT_DIR}"

echo "=== AgentOracle Eval Harness — Full Run ==="
echo "Timestamp:  ${TS}"
echo "Run ID:     ${RUN_ID}"
echo "Out dir:    ${OUT_DIR}"
echo

# Config check
: "${AGENTORACLE_API_URL:=https://agentoracle.co}"
: "${SEED:=42}"
: "${FEVER_LIMIT:=}"        # empty = full dataset
: "${AVERITEC_LIMIT:=}"     # empty = full dataset

echo "Config:"
echo "  AGENTORACLE_API_URL  = ${AGENTORACLE_API_URL}"
echo "  SEED                 = ${SEED} (used for any sampling; not passed to runner args)"
echo "  FEVER_LIMIT          = ${FEVER_LIMIT:-<full>}"
echo "  AVERITEC_LIMIT       = ${AVERITEC_LIMIT:-<full>}"
echo

# Sanity: API reachable
if ! curl -sf "${AGENTORACLE_API_URL}/health" >/dev/null; then
    echo "ERROR: AgentOracle /health is not reachable at ${AGENTORACLE_API_URL}"
    exit 1
fi

# Pin /evaluate response-shape contract before running.
# scripts/check_response_shape.py exits non-zero if /evaluate returns a payload
# that drifts from the contract _parse_response expects in clients/agentoracle_client.py
# This prevents server-side shape changes between today and results-publish from
# silently moving downstream scores.
if [[ -f scripts/check_response_shape.py ]]; then
    echo "--- Pinning /evaluate response-shape contract ---"
    python -m scripts.check_response_shape --base-url "${AGENTORACLE_API_URL}" | tee -a "${LOG_FILE}"
fi

# Helper: build --limit flag iff env var non-empty
fever_limit_flag=""
[[ -n "${FEVER_LIMIT}" ]] && fever_limit_flag="--limit ${FEVER_LIMIT}"
averitec_limit_flag=""
[[ -n "${AVERITEC_LIMIT}" ]] && averitec_limit_flag="--limit ${AVERITEC_LIMIT}"

# FEVER 1.0 paper-dev (end-to-end against /evaluate)
echo
echo "--- FEVER 1.0 paper-dev (end-to-end) ---"
python -m src.fever.runner \
    --run-id "${RUN_ID}-fever" \
    --out-dir "${OUT_DIR}" \
    --base-url "${AGENTORACLE_API_URL}" \
    --local-jsonl /data/fever/paper_dev.jsonl \
    ${fever_limit_flag} 2>&1 | tee -a "${LOG_FILE}"

# AVeriTeC dev (end-to-end against /evaluate)
echo
echo "--- AVeriTeC dev ---"
python -m src.averitec.runner \
    --run-id "${RUN_ID}-averitec" \
    --out-dir "${OUT_DIR}" \
    --base-url "${AGENTORACLE_API_URL}" \
    --local-dev-json /data/averitec/dev.json \
    ${averitec_limit_flag} 2>&1 | tee -a "${LOG_FILE}"

# Parametric-only baseline (AVeriTeC contamination delta) — no AgentOracle call
echo
echo "--- AVeriTeC parametric-only baseline (contamination control) ---"
python -m src.averitec.runner_parametric \
    --run-id "${RUN_ID}-averitec-parametric" \
    --out-dir "${OUT_DIR}" \
    --local-dev-json /data/averitec/dev.json \
    ${averitec_limit_flag} 2>&1 | tee -a "${LOG_FILE}"

# Score: FEVER
echo
echo "--- Scoring: FEVER ---"
python -m src.scoring.fever_score \
    --predictions "${OUT_DIR}/${RUN_ID}-fever/predictions.jsonl" \
    --out "${OUT_DIR}/${RUN_ID}-fever/scores.json" 2>&1 | tee -a "${LOG_FILE}"

# Score: AVeriTeC (uses both strict-URL and domain-fallback recall@k for reviewer transparency)
echo
echo "--- Scoring: AVeriTeC (with strict-URL + domain-fallback R@K) ---"
python -m src.scoring.averitec_score \
    --predictions "${OUT_DIR}/${RUN_ID}-averitec/predictions.jsonl" \
    --out "${OUT_DIR}/${RUN_ID}-averitec/scores.json" 2>&1 | tee -a "${LOG_FILE}"

# Score: contamination delta (AgentOracle vs parametric-only on AVeriTeC)
echo
echo "--- Scoring: contamination delta ---"
python -m src.scoring.contamination \
    --agentoracle "${OUT_DIR}/${RUN_ID}-averitec/predictions.jsonl" \
    --parametric "${OUT_DIR}/${RUN_ID}-averitec-parametric/predictions.jsonl" \
    --out "${OUT_DIR}/contamination_delta.json" 2>&1 | tee -a "${LOG_FILE}"

echo
echo "=== DONE ==="
echo "All results in: ${OUT_DIR}"
echo "Log:            ${LOG_FILE}"
