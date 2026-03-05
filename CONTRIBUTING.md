# Contributing to Helix

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

Thanks for contributing.

## Prerequisites
- Python 3.12+
- `uv`

## Setup
```bash
uv sync --no-editable --extra dev
```

Optional:
```bash
uv sync --no-editable --extra dev --extra zstd
```

## Development Workflow
1. Read `AGENTS.md` and follow project guardrails.
2. Keep changes scoped and spec-first:
  - update `docs/FORMAT.md` and `docs/DESIGN.md` before behavior/format changes.
3. Add or update tests with each behavior change.
4. Run quality gates locally:
```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .
PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run --no-editable python -m pytest
```

## Commit Style
Use prefixed commit messages:
- `feat: ...`
- `fix: ...`
- `improve: ...`
- `chore: ...`
- `docs: ...`
- `test: ...`
- `perf: ...`

## Security
If your change touches security-sensitive paths (container parsing, verify logic, encryption/signature, IPFS transport), include risk notes and test coverage.
For vulnerability reporting process, see `SECURITY.md`.
