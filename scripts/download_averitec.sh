#!/usr/bin/env bash
# Download AVeriTeC dataset + knowledge store from HuggingFace.
# Source: https://huggingface.co/chenxwh/AVeriTeC
# License: CC-BY-SA 4.0
#
# Total size: ~12GB (knowledge store dominates)
set -euo pipefail

DATA_DIR="${DATA_DIR:-./data/averitec}"
mkdir -p "$DATA_DIR"

echo "=== Downloading AVeriTeC dataset ==="
echo "Target dir: $DATA_DIR"
echo

if ! command -v huggingface-cli >/dev/null 2>&1; then
  echo "Installing huggingface_hub..."
  pip install --quiet "huggingface_hub[cli]"
fi

# Dev set + train set + paper test set (claim_id 0-999)
huggingface-cli download chenxwh/AVeriTeC \
  --repo-type dataset \
  --local-dir "$DATA_DIR" \
  --local-dir-use-symlinks False \
  --include "*.json" "*.csv" "*.parquet"

# Knowledge store (large — only fetch dev + paper test for now)
echo
echo "=== Downloading knowledge store (dev + paper-test) ==="
huggingface-cli download chenxwh/AVeriTeC \
  --repo-type dataset \
  --local-dir "$DATA_DIR" \
  --local-dir-use-symlinks False \
  --include "knowledge_store/dev/*" "knowledge_store/test/*"

echo
echo "=== Done ==="
echo "Files:"
find "$DATA_DIR" -type f | head -10
echo "Total size: $(du -sh "$DATA_DIR" | cut -f1)"
