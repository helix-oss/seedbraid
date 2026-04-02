---
name: test-patterns
description: >-
  Provides testing conventions and patterns for seedbraid. Use when writing or
  modifying tests in the tests/ directory. Covers pytest usage, fixture management,
  IPFS test skipping, and test command syntax.
user-invocable: false
---

# Seedbraid Testing Patterns

## Running Tests

```bash
# Full suite
PYTHONPATH=src uv run --no-editable python -m pytest

# Single test file
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_<name>.py -v

# With coverage
PYTHONPATH=src uv run --no-editable python -m pytest --cov=seedbraid
```

## Test File Conventions

- Test files: `tests/test_*.py`
- Fixtures directory: `tests/fixtures/`
- Compatibility fixtures: `tests/fixtures/compat/` (committed, version-gated)
- Fixture regeneration: `PYTHONPATH=src uv run python scripts/gen_compat_fixtures.py`

## Key Rules

1. **IPFS tests MUST skip gracefully** when `ipfs` CLI is unavailable — use pytest skip markers.
2. **MUST NOT commit large binary fixtures** — keep test data minimal and deterministic.
3. **Compatibility fixtures** in `tests/fixtures/compat/` are version-gated — regenerate only on format changes.
4. **Security-sensitive test changes** (encryption, signatures, verify) MUST include risk notes in PR.
5. **`PYTHONPATH=src`** is required for all test runs.

## Test Patterns

- Use `pytest.fixture` for shared setup.
- Use `tmp_path` for temporary file creation.
- Use `pytest.mark.skipif` for conditional skipping (IPFS, zstd).
- Group related tests in classes when they share significant setup.
- Test happy path, edge cases, boundary values, and error cases.

See `references/testing-conventions.md` for fixture examples and patterns.
