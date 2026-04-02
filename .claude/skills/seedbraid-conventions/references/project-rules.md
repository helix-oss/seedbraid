# Seedbraid Project Guardrails (Full Reference)

Source: `AGENTS.md`

## Scope and Priorities
- Keep this repository focused on Seedbraid deliverables only.
- Prioritize lossless (bit-perfect) encode/decode before optimization.
- Treat Web3 scope as IPFS publish/fetch first; registry layers are design-only unless explicitly requested.

## Engineering Rules
- Spec-first: update `docs/FORMAT.md` and `docs/DESIGN.md` before format or behavior changes.
- Determinism: CDC boundaries must be deterministic for same input and params.
- Streaming-first: avoid loading large files fully into memory in encode/decode/prime paths.
- Backward compatibility: do not silently change SBD1 semantics; bump version and document migration.

## Error Handling
- Errors must explain likely cause and next action.
- For missing genome chunks, always print missing chunk hashes/count.
- For missing IPFS CLI, print installation and verification hints.

## Quality Gates
- Run `ruff check .` and `pytest` before finalizing.
- Keep tests lightweight; avoid committing large fixtures.
- IPFS tests must skip when `ipfs` is unavailable.

## Additional Constraints (from CLAUDE.md)

- MUST NOT break SBD1 backward compatibility silently -> bump version and document migration.
- MUST keep CDC boundaries deterministic for same input and params -> reproducibility guarantee.
- MUST NOT load large files fully into memory in encode/decode/prime paths -> use streaming/bounded buffers.
- MUST NOT commit large test fixtures -> keep tests lightweight; use `tests/fixtures/compat/` for small committed fixtures only.
- MUST use conventional commit prefixes (feat/fix/improve/chore/docs/test/perf).
- NEVER skip `ruff check` and `pytest` before finalizing changes.
- Version single source of truth: `src/seedbraid/__init__.py` -> MUST NOT define version elsewhere.
