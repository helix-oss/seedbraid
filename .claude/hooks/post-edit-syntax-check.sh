#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[[ "$FILE" == *.py ]] || exit 0

RESULT=$(python3 -c "
import ast, sys
try:
    with open('$FILE') as f:
        ast.parse(f.read())
except SyntaxError as e:
    print(f'SyntaxError in $FILE: {e.msg} (line {e.lineno})')
    sys.exit(1)
" 2>&1) || true

if [ -n "$RESULT" ]; then
  echo "$RESULT"
fi
exit 0
