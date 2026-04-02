---
name: refactor
description: >-
  Plan and execute a refactoring with safety checks. Uses planner agent, then
  implements incrementally with test/lint verification. Use only when the user
  explicitly asks to refactor code.
disable-model-invocation: true
allowed-tools:
  - Agent
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - "Bash(PYTHONPATH=src uv run:*)"
  - "Bash(UV_CACHE_DIR=.uv-cache uv run:*)"
  - "Bash(git status:*)"
  - "Bash(git diff:*)"
argument-hint: "<refactoring target and goal>"
---

Plan and execute refactoring: $ARGUMENTS

Current state:
!`git status --short`
!`git diff --stat`

## Instructions

1. Spawn the **planner** agent to create a refactoring plan
2. Present the plan summary and ask for user approval before proceeding
3. After approval, implement changes incrementally
4. After each significant change, run:
   - Tests: `PYTHONPATH=src uv run --no-editable python -m pytest`
   - Lint: `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
5. Spawn the **code-reviewer** agent to verify the final result
6. Report summary of changes and verification results
