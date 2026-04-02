#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ "$FILE" == *.py ]]; then
  RESULT=$(UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check "$FILE" 2>&1) || true
  if [ -n "$RESULT" ]; then
    echo "Lint issues in $FILE: $RESULT"
  fi
fi
exit 0
