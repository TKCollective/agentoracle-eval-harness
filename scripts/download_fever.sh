#!/usr/bin/env bash
# Download FEVER 1.0 dataset.
# Source: https://fever.ai/dataset/fever.html
# License: CC-BY-SA 3.0
#
# Total size: ~45MB for claim files + ~12GB for Wikipedia dump
set -euo pipefail

DATA_DIR="${DATA_DIR:-./data/fever}"
mkdir -p "$DATA_DIR"

echo "=== Downloading FEVER 1.0 claim files ==="

# Paper-dev set (the one we've historically reported against)
curl -L -o "$DATA_DIR/paper_dev.jsonl" \
  https://fever.ai/download/fever/paper_dev.jsonl

# Paper-test set
curl -L -o "$DATA_DIR/paper_test.jsonl" \
  https://fever.ai/download/fever/paper_test.jsonl

# Shared-task dev + test (larger, more claims)
curl -L -o "$DATA_DIR/shared_task_dev.jsonl" \
  https://fever.ai/download/fever/shared_task_dev.jsonl

# Training data (optional; not used for eval but useful for sanity)
curl -L -o "$DATA_DIR/train.jsonl" \
  https://fever.ai/download/fever/train.jsonl

echo
echo "=== Downloaded ==="
ls -lh "$DATA_DIR"
wc -l "$DATA_DIR"/*.jsonl

echo
echo "NOTE: Wikipedia dump not downloaded here (~12GB). Only needed if running"
echo "      retrieval against FEVER's closed corpus. AgentOracle uses the open"
echo "      web, so we skip it. If you need it:"
echo "        curl -L -o wiki-pages.zip https://fever.ai/download/fever/wiki-pages.zip"
