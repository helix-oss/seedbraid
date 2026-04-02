---
name: phase-clear
description: >-
  Switch work phase with context preservation guidance. Supports
  investigate/plan/implement/test/review/commit phases.
allowed-tools:
  - "Bash(git:*)"
  - Read
  - Glob
argument-hint: "<next phase: investigate|plan|implement|test|review|commit>"
---

Switching to phase: $ARGUMENTS

Current state:
!`git status --short`
!`git branch --show-current`
!`git log --oneline -5`

## Instructions
0. If $ARGUMENTS is empty, list available phases and ask user to choose:
   investigate / plan / implement / test / review / commit
1. Summarize current work state briefly
2. Guide the user based on next phase:
   - **investigate** -> Use `/investigate <topic>` to start fresh exploration
   - **plan** -> Read `.docs/research/` first, then use `/plan2doc <feature>`
   - **implement** -> Read `.docs/plans/` first, implement directly
   - **test** -> Use `/test <changed files>` on modified code
   - **review** -> Use `/review-diff` to check all changes
   - **commit** -> Use `/commit` to create a conventional commit
3. Recommend running `/clear` then the next command
4. Print the exact command sequence, e.g.:
   ```
   /clear
   /catchup  (optional, to recover context)
   /<next-command>
   ```
