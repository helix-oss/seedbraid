#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Block destructive patterns at start of command, after pipe, or after semicolon
# Avoid false positives on echo/comment strings containing these patterns
if echo "$COMMAND" | grep -qE '^\s*(rm -rf|git push -f|git push --force|git reset --hard|DROP TABLE|DROP DATABASE)' || \
   echo "$COMMAND" | grep -qE '\|\s*(rm -rf)' || \
   echo "$COMMAND" | grep -qE ';\s*(rm -rf|git push -f|git reset --hard)'; then
  echo "Blocked: destructive command not allowed: $COMMAND" >&2
  exit 2
fi
exit 0
