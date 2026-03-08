---
description: "Analyze current branch state and recover working context"
---

Recover context for the current working session.

Current branch:
!`git branch --show-current`

Recent history:
!`git log --oneline -20`

Changes from main:
!`git diff --stat main`

Working tree:
!`git status --short`

## Instructions

1. Spawn the **researcher** agent to analyze:
   - What has changed on this branch vs main
   - What the changes are trying to accomplish
   - Current state of work (complete, in-progress, blocked)
2. Check for existing docs in `.docs/plans/` and `.docs/research/`
3. Report a concise summary:
   - Current situation (branch, what's been done)
   - Relevant .docs/plans files to read
   - What to do next
