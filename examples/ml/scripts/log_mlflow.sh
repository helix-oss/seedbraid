#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "${WORK_DIR}/../.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <seed.hlx> [extra args...]" >&2
  exit 1
fi

seed_path="$1"
shift

UV_CACHE_DIR="${UV_CACHE_DIR:-${REPO_DIR}/.uv-cache}" \
  uv run --project "${REPO_DIR}" --no-sync --no-editable \
  python scripts/ml_hooks.py mlflow-log "${seed_path}" "$@"
