#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# --- Destructive command patterns (T-029 C-1) ---
# Detect at any token position: start, after pipe, after semicolon, after &&/||
# Optional env/command prefix before the actual destructive command
# --force-with-lease intentionally blocked per T-029 requirements
DESTRUCTIVE='(^|[|;&])\s*(env\s+|command\s+)?(rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r|git\s+push\s+(--force|--force-with-lease|-f)\b|git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f|DROP\s+(TABLE|DATABASE))'

if echo "$COMMAND" | grep -qE "$DESTRUCTIVE"; then
  echo "Blocked: destructive command not allowed: $COMMAND" >&2
  exit 2
fi

# --- Sensitive file staging patterns (T-029 S-4) ---
# Best-effort filename check; does not catch `git add .` or `git add -A`
SENSITIVE_ADD='git\s+add\s+.*(\.(env|key|pem)\b|credentials|secret)'

if echo "$COMMAND" | grep -qE "$SENSITIVE_ADD"; then
  echo "Blocked: staging sensitive file not allowed: $COMMAND" >&2
  exit 2
fi

exit 0
