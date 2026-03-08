---
description: "Investigate codebase and generate a structured report"
argument-hint: "<topic or question to investigate>"
---

Investigate the following topic: $ARGUMENTS

Current repo state:
!`git status --short | head -20`

## Instructions

1. Spawn the **researcher** agent to investigate this topic
2. Do NOT read files directly — delegate ALL exploration to the agent
3. The researcher will save detailed findings to `.docs/research/`
4. Report the summary and output file path to the user
