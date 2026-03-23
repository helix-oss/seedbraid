# Contributing to Seedbraid

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

Thanks for contributing.

## Prerequisites
- Python 3.12+
- `uv`
- kubo daemon (for IPFS E2E tests): `ipfs daemon`

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
PYTHONPATH=src uv run --no-editable python -m pytest
```

## Documentation

Build and preview API reference docs locally:

```bash
uv sync --no-editable --extra docs
uv run mkdocs serve      # http://127.0.0.1:8000
```

Build static site:

```bash
uv run mkdocs build      # outputs to site/
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

1. Create a release branch:
   ```bash
   git checkout -b release/vX.Y.Z main
   ```
2. Update `CHANGELOG.md`: move `[Unreleased]` items to a new version section.
3. Update `src/seedbraid/__init__.py` with the new version (PEP 440, e.g., `1.0.0` or `1.1.0a1`).
4. Commit: `git commit -m "chore: bump version to X.Y.Z"`
5. Push and create a PR:
   ```bash
   git push origin release/vX.Y.Z
   gh pr create --title "chore: release vX.Y.Z" --body "Release vX.Y.Z"
   ```
6. Merge the PR via GitHub (squash or rebase). CI must pass before merge.
7. Tag the merged commit and push:
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
8. The release workflow runs automatically:
   - Verifies tag matches `__version__`
   - Runs full CI (lint, test, compat, bench-gate)
   - Builds sdist + wheel
   - Publishes to PyPI (Trusted Publishing / OIDC)
   - Creates GitHub Release with artifacts and auto-generated notes
9. Verify the [GitHub Release](../../releases) and [PyPI page](https://pypi.org/project/seedbraid/).

> **Note**: Direct push to `main` is not allowed. All changes must go through a PR.
> PyPI uses Trusted Publishing (OIDC). No API token is needed.
> Pre-release versions (containing `a`, `b`, `rc`, or `dev`) are automatically
> marked as pre-release on GitHub.

## Security
If your change touches security-sensitive paths (container parsing, verify logic, encryption/signature, IPFS transport), include risk notes and test coverage.
For vulnerability reporting process, see `SECURITY.md`.
