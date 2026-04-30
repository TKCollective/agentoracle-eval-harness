#!/usr/bin/env bash
# Runs the full eval: FEVER + AVeriTeC + parametric-only baseline.
# Writes results to /results/run_<timestamp>.json
set -euo pipefail

TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
RESULTS_FILE="/results/run_${TS}.json"
LOG_FILE="/results/run_${TS}.log"

echo "=== AgentOracle Eval Harness — Full Run ==="
echo "Timestamp: $TS"
echo "Results:   $RESULTS_FILE"
echo

# Config check
: "${AGENTORACLE_API_URL:=https://agentoracle.co}"
: "${SEED:=42}"

echo "Config:"
echo "  AGENTORACLE_API_URL = $AGENTORACLE_API_URL"
echo "  SEED                = $SEED"
echo

# Sanity: API reachable
if ! curl -sf "$AGENTORACLE_API_URL/health" >/dev/null; then
    echo "ERROR: AgentOracle /health is not reachable at $AGENTORACLE_API_URL"
    exit 1
fi

# FEVER 1.0 paper-dev
echo "--- FEVER 1.0 paper-dev (oracle-evidence mode) ---"
python -m src.fever.oracle_runner \
    --dataset /data/fever/paper_dev.jsonl \
    --out "${RESULTS_FILE}.fever_oracle" \
    --seed "$SEED" | tee -a "$LOG_FILE"

echo
echo "--- FEVER 1.0 paper-dev (end-to-end) ---"
python -m src.fever.e2e_runner \
    --dataset /data/fever/paper_dev.jsonl \
    --out "${RESULTS_FILE}.fever_e2e" \
    --seed "$SEED" | tee -a "$LOG_FILE"

# AVeriTeC dev
echo
echo "--- AVeriTeC dev ---"
python -m src.averitec.runner \
    --dataset /data/averitec/dev.json \
    --knowledge-store /data/averitec/knowledge_store/dev \
    --out "${RESULTS_FILE}.averitec_dev" \
    --seed "$SEED" | tee -a "$LOG_FILE"

# Parametric-only baseline (no AgentOracle — pure LLM)
echo
echo "--- Parametric-only baseline (FEVER) ---"
python -m src.fever.e2e_runner \
    --dataset /data/fever/paper_dev.jsonl \
    --out "${RESULTS_FILE}.fever_parametric" \
    --seed "$SEED" \
    --no-retrieval | tee -a "$LOG_FILE"

# Aggregate
echo
echo "--- Aggregating results ---"
python -m src.scoring.aggregate \
    --inputs "${RESULTS_FILE}".* \
    --out "${RESULTS_FILE}" | tee -a "$LOG_FILE"

echo
echo "=== DONE ==="
echo "Results:   $RESULTS_FILE"
echo "Log:       $LOG_FILE"
