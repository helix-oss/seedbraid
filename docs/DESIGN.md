# Helix v2 Design

## Step 0 Findings and Migration Policy
Repository scan on 2026-02-08 found no application source files. Only Git metadata existed.

Migration policy:
- Keep: none (no legacy implementation present).
- Replace: n/a.
- New baseline: implement Helix v2 from scratch under `src/helix` with spec-first docs.

## Goals
- Bit-perfect reconstruction (`encode -> decode` SHA-256 match).
- Better dedup under shifted edits using CDC.
- Binary seed portability and machine-readability (HLX1 container).
- Web3 transport via IPFS CLI publish/fetch.

## Non-Goals (This Iteration)
- Approximate search, generative synthesis, advanced delta encoding.
- On-chain registry, ENS mapping, storage deal management.
- End-to-end encryption defaults.

## Architecture
- `chunking.py`: deterministic `fixed`, `cdc_buzhash`, `cdc_rabin` chunkers.
- `storage.py`: pluggable storage interface, SQLite implementation for genome.
- `container.py`: HLX1 binary TLV serialization/parsing + integrity checks.
- `codec.py`: encode/decode/verify/prime workflows and genome snapshot/restore.
- `ipfs.py`: subprocess wrapper for `ipfs add/cat/pin`.
- `cli.py`: Typer command surface.

## Why Binary Recipe + Manifest
- Binary recipe reduces size and parse overhead compared to verbose textual formats.
- Manifest keeps operator-visible metadata, provenance, and verification expectations.
- TLV allows forward-compatible section growth.

## Why CDC
- Fixed-size chunking breaks dedup on byte-shift edits.
- CDC anchors boundaries on rolling fingerprints, improving chunk reuse across insertions.
- Deterministic rolling hash keeps reproducibility.

## Memory Model
- Encode/decode/prime process streams in bounded buffers.
- Genome chunks are read/written per-operation; no full-file buffering in core path.
- Exception: CLI-level helper logic may materialize small metadata structures (hash table/ops).

## Trade-offs
- SQLite chosen for portability over peak write throughput.
- Default `zlib` avoids optional dependency friction; `zstd` supported when installed.
- Portable seeds can be larger because unknown chunks are embedded.
- Integrity uses CRC32 + SHA-256 digests.
- Optional seed signatures use HMAC-SHA256 in this iteration (`helix sign` and `verify --require-signature`).
- Optional encryption uses HLE1 wrapper around HLX1 payload for backward-compatible rollout.
- Optional `manifest-private` mode reduces metadata leakage at the cost of weaker post-restore provenance metadata.
- `helix publish` warns on unencrypted seed publication to reduce accidental public leakage.
- IPFS fetch path includes retry/backoff and optional HTTP gateway fallback for resilience.
- `helix pin-health` provides operator-visible local pin and block availability checks.

## Assumptions
- `ipfs` CLI installed/configured when publish/fetch is used.
- Genome path points to writable location.
- Single-process access for SQLite baseline (no aggressive concurrency tuning).

## Future Extensions
- Near-match and delta hooks:
  - add matcher interface to score similar chunks by locality-sensitive fingerprint.
  - add delta opcodes referencing base chunk + patch payload.
- Generative hooks:
  - synthetic chunk provider interface keyed by recipe metadata.
- Registry layer:
  - map logical seed names to CIDs (ENS or on-chain pointer) as separate module.

## Optional Gene Transport
- Implemented minimal `export-genes` / `import-genes` for operational recovery.
- Purpose: move required chunk payloads between genomes without shipping full databases.
- Trade-off: no compression/encryption in initial format; can be layered later if needed.

## Genome Snapshot/Restore (R-01)
- Add `helix genome snapshot` to export all stored chunks as `HGS1` binary snapshot.
- Add `helix genome restore` to import chunk payloads into a target genome.
- Goal: operational DR workflow so non-portable seeds remain recoverable.
