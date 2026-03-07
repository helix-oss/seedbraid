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

## Releasing

Only maintainers can create releases.

1. Update `CHANGELOG.md`: move `[Unreleased]` items to a new version section.
2. Update `src/helix/__init__.py` with the new version (PEP 440, e.g., `1.0.0` or `1.1.0a1`).
3. Commit: `git commit -m "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin main && git push origin vX.Y.Z`
6. The release workflow runs automatically:
   - Verifies tag matches `__version__`
   - Runs full CI (lint, test, compat, bench-gate)
   - Builds sdist + wheel
   - Publishes to PyPI (Trusted Publishing / OIDC)
   - Creates GitHub Release with artifacts and auto-generated notes
7. Verify the [GitHub Release](../../releases) and [PyPI page](https://pypi.org/project/helix/).

> **Note**: PyPI uses Trusted Publishing (OIDC). No API token is needed.
> Pre-release versions (containing `a`, `b`, `rc`, or `dev`) are automatically
> marked as pre-release on GitHub.

## Security
If your change touches security-sensitive paths (container parsing, verify logic, encryption/signature, IPFS transport), include risk notes and test coverage.
For vulnerability reporting process, see `SECURITY.md`.
