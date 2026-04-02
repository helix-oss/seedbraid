---
name: phase-clear
description: >-
  Switch work phase with context preservation guidance. Auto-detects current
  phase from git state and .docs/ contents when no argument provided.
  Supports investigate/plan/implement/test/review/commit phases.
allowed-tools:
  - "Bash(git:*)"
  - "Bash(ls:*)"
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

### 0. Auto-Detection (when $ARGUMENTS is empty)

If $ARGUMENTS is empty, auto-detect the current phase by checking these conditions in order.
Recommend the first matching phase:

1. **No `.docs/research/` files for current topic** → suggest **investigate**
   - Check: `ls .docs/research/ 2>/dev/null` is empty or has no files related to current branch
2. **Research exists, no plans** → suggest **plan**
   - Check: `.docs/research/` has files BUT `.docs/plans/` has no related files
3. **Plans exist, no code diff from main** → suggest **implement**
   - Check: `.docs/plans/` has files BUT `git diff main --name-only` shows no `src/` changes
4. **Code diff exists, no test changes** → suggest **test**
   - Check: `git diff main --name-only` shows `src/` changes BUT no `tests/` changes
5. **Tests exist, no review files** → suggest **review**
   - Check: Both `src/` and `tests/` changes BUT `.docs/reviews/` has no recent review
6. **Review done, uncommitted changes** → suggest **commit**
   - Check: `.docs/reviews/` has recent review AND `git status --porcelain` shows uncommitted changes

Present the detection result with reasoning. Ask user to confirm or choose differently.

### 1. Summarize current work state briefly
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
