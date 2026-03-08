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
CID_PATH="${SB_DVC_CID_PATH:-${WORK_DIR}/artifacts/metadata/seed.cid}"
FETCHED_PATH="${SB_DVC_FETCHED_PATH:-${WORK_DIR}/artifacts/fetched/current.sbd}"

mkdir -p "$(dirname "${CID_PATH}")" "$(dirname "${FETCHED_PATH}")"

if [[ ! -s "${CID_PATH}" ]]; then
  cid="$(run_seedbraid publish "${SEED_PATH}" --no-pin | tail -n 1 | tr -d '[:space:]')"
  if [[ -z "${cid}" ]]; then
    echo "failed: seedbraid publish did not return a CID" >&2
    exit 1
  fi
  printf '%s\n' "${cid}" > "${CID_PATH}"
fi

cid="$(tr -d '[:space:]' < "${CID_PATH}")"
if [[ -z "${cid}" ]]; then
  echo "failed: CID metadata is empty at ${CID_PATH}" >&2
  exit 1
fi

run_seedbraid fetch "${cid}" --out "${FETCHED_PATH}"
