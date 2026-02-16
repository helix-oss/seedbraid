# Helix Implementation Plan

## Goal
Implement reference-based reconstruction + shift-robust dedup with lossless reconstruction and IPFS seed transport.

## Current Repository State (Step 0)
- Existing code: none (repository initialized but empty).
- Migration policy: no legacy code to preserve; implement fresh layout under `src/helix`.

## Task Breakdown
1. Spec-first docs
- Create `docs/FORMAT.md`, `docs/DESIGN.md`, `docs/THREAT_MODEL.md`, and this plan.
- Freeze HLX1 container and recipe semantics before coding.

2. Core package skeleton
- `src/helix` package with CLI (`typer`) and modules for chunking, storage, container, codec, IPFS.

3. CDC implementation
- Provide deterministic `cdc_buzhash` and `cdc_rabin` plus `fixed`.
- Stream input using bounded buffers.

4. Genome storage
- SQLite backend with interface abstraction.
- Keys: SHA-256 chunk hash (32 bytes), values: chunk bytes.

5. HLX1 container
- Binary container with magic/version + TLV sections.
- Manifest (JSON + compression), recipe (binary), optional RAW payloads, integrity section.

6. Commands
- `encode/decode/verify/prime/publish/fetch` with actionable errors.

7. Testing and benchmark
- Roundtrip, CDC determinism, seed compatibility, prime/verify, IPFS optional tests.
- Add shifted-byte dedup benchmark script and README reproducible commands.

## Key Design Choices
- Compression: `zlib` default; `zstd` supported when optional dependency is installed.
- Portable mode: unknown chunks are embedded as RAW payloads and can decode without genome.
- Learn mode default ON: unknown chunks are inserted into genome.

## Assumptions
- Python 3.12+ runtime.
- `ipfs` CLI may be absent; publish/fetch must fail clearly and tests should skip.
- No encryption in initial baseline; security posture documented in threat model.

## Change Log
- 2026-02-08: Initial plan created from empty repository.
