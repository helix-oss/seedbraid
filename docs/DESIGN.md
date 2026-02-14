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
- `helix doctor` provides preflight diagnostics for IPFS, genome path, and compression support.
- Error output is standardized with stable `HELIX_E_*` codes and next-action hints.
- Compatibility governance uses committed fixture seeds and regression tests as
  release gates; format evolution must preserve read compatibility or bump version.
- Performance governance adds benchmark gates for CDC reuse gain, seed-size ratio,
  and encode throughput (`scripts/bench_gate.py`).

## CI Integration Pack (HLX-ECO-001)
- Primary workflow lives at `.github/workflows/ci.yml`.
- CI jobs are separated into lint (`ruff check .`), full tests
  (`python -m pytest`), compatibility fixtures
  (`python -m pytest tests/test_compat_fixtures.py`), and benchmark gates
  (`scripts/bench_gate.py`).
- Benchmark gate is PR-blocking: non-zero exit from `bench_gate.py` fails the
  workflow and surfaces explicit gate violation lines in logs.
- Optional publish workflow lives at `.github/workflows/publish-seed.yml`, is
  manual (`workflow_dispatch`), and performs `encode -> verify --strict ->
  publish` with `dry_run=true` as the safe default.
- In real publish mode (`dry_run=false`), workflow installs Kubo (`ipfs` CLI)
  on runner before publish, verifies release tag signature state via GitHub API,
  and verifies archive checksum before extraction so hosted runners can execute
  IPFS operations safely.
- CLI includes `helix gen-encryption-key` for operator-safe generation of
  `HELIX_ENCRYPTION_KEY` secrets from command line workflows.

## Remote Pinning Adapter (HLX-ECO-002)
- Add provider-agnostic remote pin adapter interface for CID durability workflows.
- First provider implementation targets Pinning Services API-compatible endpoints.
- `helix publish` can optionally trigger remote pin after local CID creation.
- CLI adds explicit remote-pin options for provider, endpoint/token, timeout, and retries.
- `helix pin remote-add` allows pinning an existing CID without re-publishing seed bytes.
- Remote pin failures use dedicated `HELIX_E_*` operator codes with actionable hints.

## DVC Workflow Bridge (HLX-ECO-003)
- Add `examples/dvc/` as a minimal, script-driven DVC pipeline for
  `encode -> verify --strict -> fetch` Helix seed workflows.
- DVC bridge is operational glue only. It does not change chunking, genome storage,
  HLX1/HLE1 serialization, or integrity semantics.
- Recommended pipeline artifact layout:
  - `artifacts/seed/current.hlx`: encoded seed tracked by DVC.
  - `artifacts/genome/snapshot.hgs`: reproducible genome snapshot for handoff/backup.
  - `artifacts/metadata/*`: sidecar metadata (`seed.cid`, `verify.ok`, digest files).
  - `artifacts/fetched/current.hlx`: fetched seed for downstream stages.
- Verify stage must call `helix verify --strict` so integrity mismatch (or missing
  chunks) fails DVC reproduction early.
- Out of scope remains custom DVC plugin/registry integration.

## OCI/ORAS Artifact Distribution (HLX-ECO-004)
- Add ORAS bridge scripts for pushing/pulling Helix seed artifacts via OCI
  registry references (`registry/repository:tag`).
- Define and document Helix media/annotation conventions so registry metadata is
  machine-readable across providers:
  - artifact type: `application/vnd.helix.seed.v1`
  - layer media type: `application/vnd.helix.seed.layer.v1+hlx`
  - annotations: source SHA-256, chunker name, manifest-private flag.
- Push flow extracts manifest metadata from seed and writes OCI annotations.
- Pull flow restores the seed file from registry artifact payload without changing
  seed bytes; verification remains `helix verify --strict`.
- Provider usage docs cover GHCR/ECR/GAR authentication entry points only.
- Out of scope remains provider-specific IAM automation.

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
