---
name: seedbraid-conventions
description: >-
  Provides seedbraid project conventions and constraints. Applied automatically
  when working on seedbraid source code, tests, or documentation. Covers Python
  3.12+ standards, ruff linting, spec-first policy, streaming-first architecture,
  and conventional commit format. Use this skill whenever modifying or reviewing
  seedbraid code.
user-invocable: false
---

# Seedbraid Project Conventions

## Engineering Rules

- **Spec-first**: Update `docs/FORMAT.md` and `docs/DESIGN.md` before any format or behavior change.
- **Determinism**: CDC boundaries must be deterministic for same input and params.
- **Streaming-first**: Never load large files fully into memory in encode/decode/prime paths. Use streaming/bounded buffers.
- **Backward compatibility**: Do not silently change SBD1 semantics. Bump version and document migration.
- **Version source of truth**: `src/seedbraid/__init__.py`. Do not define version elsewhere.

## Python Standards

- Python >=3.12
- Linter: ruff (line-length=79, target-version=py312), config in `pyproject.toml`
- Test framework: pytest
- Package manager: uv

## Quality Gates

- Run `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .` before finalizing.
- Run `PYTHONPATH=src uv run --no-editable python -m pytest` before finalizing.
- Keep tests lightweight; avoid committing large fixtures.
- IPFS tests must skip when `ipfs` CLI is unavailable.

## Conventional Commits

Use prefixes: `feat`, `fix`, `improve`, `chore`, `docs`, `test`, `perf`.

## Error Handling

- Errors must explain likely cause and next action.
- For missing genome chunks: print missing chunk hashes/count.
- For missing IPFS CLI: print installation and verification hints.

## Project Scope

- Keep focused on seedbraid deliverables only.
- Prioritize lossless (bit-perfect) encode/decode before optimization.
- Web3 scope: IPFS publish/fetch first; registry layers are design-only unless explicitly requested.

See `references/project-rules.md` for the full guardrails document.
