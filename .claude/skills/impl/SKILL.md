---
name: impl
description: >-
  Implement the latest plan with optional additional instructions.
  Runs implementation, lint, test loop, and simplify review.
  Use after /scout or /plan2doc to execute the plan.
  Optionally accepts a plan file path as the first argument.
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
argument-hint: "[plan file path or additional instructions]"
---

Implement the latest plan.
User arguments: $ARGUMENTS

## Pre-computed Context

Latest plan:
!`ls -t .docs/plans/*.md 2>/dev/null | head -1`

Latest research:
!`ls -t .docs/research/*.md 2>/dev/null | head -1`

Current state:
!`git status --short`

## Phase 1: Plan Loading

1. Determine the plan file:
   - If `$ARGUMENTS` starts with `.docs/plans/` → use it as the plan file path. Remaining text is additional instructions.
   - Otherwise → use the latest plan file shown above. `$ARGUMENTS` is treated as additional instructions.
   - If no plan file exists, print "No plan found in .docs/plans/. Run /scout or /plan2doc first." and stop.
2. Read the plan file content.
3. If a related research file exists in `.docs/research/`, read it for additional context.
4. If additional instructions are provided, integrate them with the plan (additional instructions take priority on conflicts).
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

## Phase 4.5: Security Scan (Security category only)

15. Check the plan file's Category field (already read in Step 2 — look for `| Category |` table row in the header).
    - If Category is **Security** (case-insensitive match): proceed to step 16.
    - If Category is absent or any other value: print "Skipped security-scan (Category != Security)" and go to Phase 5.
16. Print "Security category detected — running /security-scan automatically".
17. Call `/security-scan` via the Skill tool (no arguments — audits all security-sensitive modules).
18. Display the security-scan result summary.
    - If Critical or High findings are reported: warn the user and recommend fixing before shipping.
    - Regardless of findings, continue the implementation flow (security-scan is advisory).

## Phase 5: Simplify

19. Check the plan file's Size field (already read in Step 2 — look for `| Size |` table row in the header).
    - If Size is **S**: skip simplify — print "Skipped simplify (Size=S)" and go to Phase 7.
    - Otherwise (M/L/XL or not found → treat as M): call `/simplify` via the Skill tool.
20. Print the simplify result summary (or the skip message).

## Phase 6: Post-simplify Verification

21. Check `git diff --stat` to see if simplify made changes.
22. If changes were made, re-run lint + tests:
    - `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
    - `PYTHONPATH=src uv run --no-editable python -m pytest -q`
23. If post-simplify tests fail, fix once and re-run. If still failing, report to the user for manual resolution.

## Phase 7: Summary

24. Run `git status -s` and display the output.
25. Print a summary including:
    - Plan file executed
    - Files changed or created
    - Test results (pass/fail count)
    - Simplify review outcome
    - "Review the changes above, then run `/ship` to commit and create PR"

## Error Handling

- **No plan**: Print "No plan found in .docs/plans/. Run /scout or /plan2doc first." and stop.
- **Dirty working tree**: Warn user about unrelated changes, ask whether to continue.
- **Lint 3x failure**: Print failures and stop. Code remains in place.
- **Test 3x failure**: Print failures and stop. Code remains in place.
- **Simplify failure**: Print warning and continue (implementation + tests are already complete).
- **Post-simplify test failure**: Report to user for manual resolution.
- **Security-scan failure**: Print warning and continue (implementation + tests are already complete). Recommend manual `/security-scan` after fixing reported issues.
