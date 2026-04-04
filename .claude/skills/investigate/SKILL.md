---
name: investigate
description: >-
  Investigate codebase topics via researcher agent. Saves structured findings
  to .docs/research/. Use when exploring code, tracking dependencies, or
  understanding architecture.
context: fork
agent: researcher
argument-hint: "<topic or question to investigate>"
---

Investigate the following topic: $ARGUMENTS

Current repo state:
!`git status --short | head -20`

## Instructions

1. Investigate this topic thoroughly
2. Use Grep/Glob to find relevant code, then Read to understand it
3. If investigating a ticket, include the ticket's Size (S/M/L/XL) in the research file header
4. Write ALL detailed findings to `.docs/research/`
5. Return a brief executive summary with the output file path
