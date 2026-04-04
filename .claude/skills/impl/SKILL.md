---
name: impl
description: >-
  Implement the latest plan with optional additional instructions.
  Runs implementation, lint, test loop, and simplify review.
  Use after /scout or /plan2doc to execute the plan.
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - "Bash(UV_CACHE_DIR=.uv-cache uv run:*)"
  - "Bash(PYTHONPATH=src uv run:*)"
  - "Bash(git status:*)"
  - "Bash(git diff:*)"
  - "Bash(mkdir:*)"
  - "Bash(ls:*)"
  - Skill
argument-hint: "[additional instructions (optional)]"
---

Implement the latest plan.
Additional instructions from user: $ARGUMENTS

## Pre-computed Context

Latest plan:
!`ls -t .docs/plans/*.md 2>/dev/null | head -1`

Latest research:
!`ls -t .docs/research/*.md 2>/dev/null | head -1`

Current state:
!`git status --short`

Current branch:
!`git branch --show-current`

## Phase 1: Plan Loading

1. If no plan file is listed above, print "No plan found in .docs/plans/. Run /scout or /plan2doc first." and stop.
2. Read the latest plan file content.
3. If a related research file exists in `.docs/research/`, read it for additional context.
4. If `$ARGUMENTS` contains additional instructions, integrate them with the plan (additional instructions take priority on conflicts).
5. If the working tree has uncommitted changes unrelated to the plan, warn the user before proceeding.

## Phase 2: Implementation

6. Follow the plan's steps to implement code changes, including test code.
7. Adhere to project constraints: streaming-first (no full-file buffering), SBD1 backward compatibility, ruff line-length=79, Python 3.12+.
8. If the plan involves format or behavior changes, update `docs/FORMAT.md` and/or `docs/DESIGN.md` first (spec-first policy).

## Phase 3: Lint (max 3 attempts)

9. Run lint: `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
10. If lint fails, fix the issues and re-run. Repeat up to 3 attempts.
11. If lint still fails after 3 attempts, report failures and stop.

## Phase 4: Test (max 3 attempts)

12. Run tests: `PYTHONPATH=src uv run --no-editable python -m pytest -q`
13. If tests fail, fix the issues and re-run. Repeat up to 3 attempts.
14. If tests still fail after 3 attempts, report failures and stop.

## Phase 5: Simplify

15. Call `/simplify` via the Skill tool to review the changes.
16. Print the simplify result summary.

## Phase 6: Post-simplify Verification

17. Check `git diff --stat` to see if simplify made changes.
18. If changes were made, re-run lint + tests:
    - `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
    - `PYTHONPATH=src uv run --no-editable python -m pytest -q`
19. If post-simplify tests fail, fix once and re-run. If still failing, report to the user for manual resolution.

## Phase 7: Summary

20. Print a summary including:
    - Plan file executed
    - Files changed or created (`git diff --stat`)
    - Test results (pass/fail count)
    - Simplify review outcome
    - Recommended next step: `/ship` to commit and create PR

## Error Handling

- **No plan**: Print "No plan found in .docs/plans/. Run /scout or /plan2doc first." and stop.
- **Dirty working tree**: Warn user about unrelated changes, ask whether to continue.
- **Lint 3x failure**: Print failures and stop. Code remains in place.
- **Test 3x failure**: Print failures and stop. Code remains in place.
- **Simplify failure**: Print warning and continue (implementation + tests are already complete).
- **Post-simplify test failure**: Report to user for manual resolution.
