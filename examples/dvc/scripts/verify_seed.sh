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

SEED_PATH="${SB_DVC_SEED_PATH:-${WORK_DIR}/artifacts/seed/current.sbd}"
GENOME_PATH="${SB_DVC_GENOME_PATH:-${WORK_DIR}/artifacts/genome}"
VERIFY_OK_PATH="${SB_DVC_VERIFY_OK_PATH:-${WORK_DIR}/artifacts/metadata/verify.ok}"

mkdir -p "$(dirname "${VERIFY_OK_PATH}")"

run_seedbraid verify "${SEED_PATH}" --genome "${GENOME_PATH}" --strict
printf 'ok\n' > "${VERIFY_OK_PATH}"
