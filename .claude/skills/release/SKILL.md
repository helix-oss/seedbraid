---
name: release
description: >-
  Create a release: version bump, changelog, PR, tag, and GitHub Release.
  Requires gh command. Use only when the user explicitly requests a release.
disable-model-invocation: true
model: sonnet
allowed-tools:
  - "Bash(git:*)"
  - "Bash(gh:*)"
  - "Bash(PYTHONPATH=src uv run:*)"
  - "Bash(UV_CACHE_DIR=.uv-cache uv run:*)"
  - Read
  - Edit
  - Grep
  - Glob
argument-hint: "[tag=vX.Y.Z] [rev=COMMIT]"
---

Create a release for this project.
User arguments: $ARGUMENTS

## Argument Parsing

Parse `$ARGUMENTS` for optional key=value pairs:
- `tag=vX.Y.Z` — the release tag (e.g. `tag=v1.0.0b2`). Strip the `v` prefix when used as a version string in code.
- `rev=COMMIT` — the target revision (commit SHA or ref). Default: HEAD of the default branch.

If neither is provided, follow the interactive flow in Phase 1.

## Project Context

Adapt ALL steps below to these project-specific settings.
When reusing this command for another project, update this section AND the allowed-tools in the frontmatter.

- **Language/Tooling**: Python, uv, ruff, pytest
- **Version file**: `src/seedbraid/__init__.py` (`__version__` variable)
- **Versioning scheme**: PEP 440 (e.g. `1.0.0`, `1.0.0b1`, `1.0.0rc1`)
- **Changelog**: `CHANGELOG.md` (Keep a Changelog format)
- **Commit convention**: Conventional Commits (feat/fix/improve/chore/docs/test/perf)
- **Default branch**: main (protected — direct push blocked, must use PR)
- **Merge strategy**: `--squash` preferred. Fallback: `--rebase`. NEVER `--merge`.
- **Release workflow**: `.github/workflows/release.yml` (tag push → CI → build → publish → release)
- **Publishing target**: PyPI via Trusted Publishing
- **Lint command**: `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .`
- **Test command**: `PYTHONPATH=src uv run --no-editable python -m pytest -q`
- **Pre-release indicator**: version contains `a`, `b`, `rc`, or `dev`

## Pre-computed Context

Current version:
!`grep -m1 '__version__' src/seedbraid/__init__.py`

Last tag:
!`git describe --tags --abbrev=0 2>/dev/null || echo "(no tags)"`

Commits since last tag:
!`git log $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~10)..HEAD --oneline`

## Steps

Read `references/release-workflow.md` for the full release workflow (Phase 0-6 and Error Handling).
