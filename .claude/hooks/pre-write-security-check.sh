#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Security-sensitive paths: require confirmation before editing
case "$FILE" in
  */container.py|*/codec.py|*/ipfs.py|*/ipfs_http.py|*/ipfs_chunks.py|\
  */cid.py|*/chunk_manifest.py|*/pinning.py|\
  */FORMAT.md|*/THREAT_MODEL.md)
    echo "WARNING: Security-sensitive file: $(basename "$FILE"). Read docs/THREAT_MODEL.md before modifying." >&2
    # Warning only -- allow the edit to proceed
    ;;
esac
exit 0
