#!/usr/bin/env bash
set -euo pipefail

BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
CHANGED=$(git status --short 2>/dev/null | wc -l | tr -d ' ')

CONTEXT="Branch: ${BRANCH} | Changed files: ${CHANGED}"

# Read active feature from project memory
MEMORY_DIR="$HOME/.claude/projects/-$(echo "$PWD" | tr '/' '-')/memory"
if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
  ACTIVE=$(grep -A1 "Active Feature" "$MEMORY_DIR/MEMORY.md" 2>/dev/null | tail -1 | sed 's/^- //' | head -c 200)
  [ -n "$ACTIVE" ] && CONTEXT="${CONTEXT} | Active: ${ACTIVE}"
fi

# Find latest plan document
LATEST_PLAN=$(ls -t .docs/plans/*.md 2>/dev/null | head -1)
[ -n "${LATEST_PLAN:-}" ] && CONTEXT="${CONTEXT} | Latest Plan: $(basename "$LATEST_PLAN")"

# Output as additionalContext JSON
jq -n --arg ctx "$CONTEXT" '{"additionalContext": $ctx}'
