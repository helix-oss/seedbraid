# Helix

Reference-based file reconstruction with CDC chunking, binary HLX1 seed format, and IPFS transport.

## Tech Stack
- Python >=3.12, Typer (CLI), SQLite (genome storage)
- uv (package manager), ruff (linter), pytest (tests)
- Optional: zstandard (zstd compression), ipfs CLI (publish/fetch)

## Commands
- `uv sync --no-editable --extra dev` — install dev dependencies
- `uv sync --no-editable --extra dev --extra zstd` — install with zstd support
- `PYTHONPATH=src uv run --no-editable python -m pytest` — run tests
- `UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .` — lint
- `uv run helix <command>` — run CLI (encode, decode, verify, publish, fetch, doctor)
- `PYTHONPATH=src uv run python scripts/bench_gate.py` — performance benchmark gate (CI)
- `PYTHONPATH=src uv run python scripts/gen_compat_fixtures.py` — regenerate compat fixtures

## Architecture
CDC anchors chunk boundaries on rolling hash fingerprints for byte-shift-resilient dedup.
SQLite genome stores chunks for portability over peak throughput. HLX1 binary TLV format
enables forward-compatible section growth. Design details in `docs/DESIGN.md`.

- `src/helix/` — all source: cli, codec, chunking, container, storage, ipfs, oci, mlhooks
- `tests/` — pytest suite; IPFS tests auto-skip when `ipfs` CLI unavailable
- `scripts/` — bench_gate, compat fixture generation, ML/OCI bridge utilities
- `docs/` — FORMAT.md (binary spec), DESIGN.md, THREAT_MODEL.md, PERFORMANCE.md
- `examples/` — integration examples: dvc/, oci/, ml/

## Constraints
- MUST update `docs/FORMAT.md` and `docs/DESIGN.md` before any format or behavior change → spec-first policy per AGENTS.md
- MUST NOT break HLX1 backward compatibility silently → bump version and document migration instead
- MUST keep CDC boundaries deterministic for same input and params → reproducibility guarantee
- MUST NOT load large files fully into memory in encode/decode/prime paths → use streaming/bounded buffers
- MUST NOT commit large test fixtures → keep tests lightweight; use `tests/fixtures/compat/` for small committed fixtures only
- MUST use conventional commit prefixes (feat/fix/improve/chore/docs/test/perf) → per CONTRIBUTING.md
- NEVER skip `ruff check` and `pytest` before finalizing changes → CI will block on failures
- Version single source of truth: `src/helix/__init__.py` → MUST NOT define version elsewhere

## Reference Docs
- When modifying binary format or container logic → read `docs/FORMAT.md`
- When changing architecture or adding features → read `docs/DESIGN.md`
- When touching security-sensitive code (verify, encryption, signatures, IPFS) → read `docs/THREAT_MODEL.md`
- When adjusting performance thresholds → read `docs/PERFORMANCE.md`
- When onboarding or reviewing guardrails → read `AGENTS.md`
- For error code conventions → read `docs/ERROR_CODES.md`
