#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "${WORK_DIR}/../.." && pwd)"

run_seedbraid() {
  if [[ -n "${SB_DVC_SEEDBRAID_BIN:-}" ]]; then
    "${SB_DVC_SEEDBRAID_BIN}" "$@"
    return
  fi

  UV_CACHE_DIR="${UV_CACHE_DIR:-${REPO_DIR}/.uv-cache}" \
    uv run --project "${REPO_DIR}" --no-sync --no-editable seedbraid "$@"
}

INPUT_PATH="${SB_DVC_INPUT_PATH:-${WORK_DIR}/data/input.bin}"
GENOME_PATH="${SB_DVC_GENOME_PATH:-${WORK_DIR}/artifacts/genome}"
SEED_PATH="${SB_DVC_SEED_PATH:-${WORK_DIR}/artifacts/seed/current.sbd}"
SNAPSHOT_PATH="${SB_DVC_SNAPSHOT_PATH:-${WORK_DIR}/artifacts/genome/snapshot.sgs}"

mkdir -p "$(dirname "${SEED_PATH}")" "${GENOME_PATH}" "$(dirname "${SNAPSHOT_PATH}")"

run_seedbraid encode \
  "${INPUT_PATH}" \
  --genome "${GENOME_PATH}" \
  --out "${SEED_PATH}" \
  --chunker cdc_buzhash \
  --avg 65536 \
  --min 16384 \
  --max 262144 \
  --learn \
  --no-portable \
  --compression zlib

run_seedbraid genome snapshot --genome "${GENOME_PATH}" --out "${SNAPSHOT_PATH}"
