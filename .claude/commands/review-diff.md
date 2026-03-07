---
description: "Review current changes with multi-agent analysis"
argument-hint: "[branch or commit range (optional)]"
---

Review the current code changes. Target: $ARGUMENTS

Staged changes:
!`git diff --cached --stat`

Unstaged changes:
!`git diff --stat`

Changed files:
!`git diff --cached --name-only && git diff --name-only`

## Instructions

1. Spawn the **code-reviewer** agent to review all changes
2. If security-sensitive files are changed (container, codec, ipfs, pinning), also spawn the **security-scanner** agent in parallel
3. Do NOT read files directly — delegate ALL review to agents
4. Aggregate results by severity: Critical > Warning > Suggestion
5. Report structured review summary to the user
