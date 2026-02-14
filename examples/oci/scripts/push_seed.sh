#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "${WORK_DIR}/../.." && pwd)"

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <seed.hlx> <registry/repository:tag> [extra args...]" >&2
  exit 1
fi

seed_path="$1"
reference="$2"
shift 2

UV_CACHE_DIR="${UV_CACHE_DIR:-${REPO_DIR}/.uv-cache}" \
  uv run --project "${REPO_DIR}" --no-sync --no-editable \
  python scripts/oras_seed.py push "${seed_path}" "${reference}" "$@"
