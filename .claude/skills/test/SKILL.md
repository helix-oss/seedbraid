---
name: test
description: >-
  Create and run tests for specified files or features using the test-writer
  agent. Follows existing pytest patterns in the tests/ directory.
context: fork
agent: test-writer
argument-hint: "<file path or feature name to test>"
---

Create and run tests for: $ARGUMENTS

## Instructions

1. Examine existing tests in `tests/` to understand patterns and conventions
2. Design test cases covering: happy path, edge cases, boundary values, error cases
3. Write tests following existing patterns (pytest, fixtures in `tests/fixtures/`)
4. Run tests with: `PYTHONPATH=src uv run --no-editable python -m pytest {test_file} -v`
5. Fix any failing tests before returning
6. Report test file paths and pass/fail results
