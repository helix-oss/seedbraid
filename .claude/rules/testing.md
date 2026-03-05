---
paths:
  - "tests/**"
---
# Testing Rules

- Run tests: `PYTHONPATH=src uv run --no-editable python -m pytest`
- Run single test: `PYTHONPATH=src uv run --no-editable python -m pytest tests/test_<name>.py`
- IPFS-dependent tests MUST skip gracefully when `ipfs` CLI is unavailable → use pytest skip markers
- Compatibility fixtures in `tests/fixtures/compat/` are committed and version-gated → regenerate with `scripts/gen_compat_fixtures.py` only when format changes
- MUST NOT commit large binary fixtures → keep test data minimal and deterministic
- Security-sensitive test changes (encryption, signatures, verify) MUST include risk notes in PR
