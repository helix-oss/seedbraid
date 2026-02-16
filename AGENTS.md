# Helix Project Guardrails

## Scope and Priorities
- Keep this repository focused on Helix deliverables only.
- Prioritize lossless (bit-perfect) encode/decode before optimization.
- Treat Web3 scope as IPFS publish/fetch first; registry layers are design-only unless explicitly requested.

## Engineering Rules
- Spec-first: update `docs/FORMAT.md` and `docs/DESIGN.md` before format or behavior changes.
- Determinism: CDC boundaries must be deterministic for same input and params.
- Streaming-first: avoid loading large files fully into memory in encode/decode/prime paths.
- Backward compatibility: do not silently change HLX1 semantics; bump version and document migration.

## Error Handling
- Errors must explain likely cause and next action.
- For missing genome chunks, always print missing chunk hashes/count.
- For missing IPFS CLI, print installation and verification hints.

## Quality Gates
- Run `ruff check .` and `pytest` before finalizing.
- Keep tests lightweight; avoid committing large fixtures.
- IPFS tests must skip when `ipfs` is unavailable.
