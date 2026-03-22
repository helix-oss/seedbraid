# Seedbraid Design

## Step 0 Findings and Migration Policy
Repository scan on 2026-02-08 found no application source files. Only Git metadata existed.

Migration policy:
- Keep: none (no legacy implementation present).
- Replace: n/a.
- New baseline: implement Seedbraid from scratch under `src/seedbraid` with spec-first docs.

## Goals
- Bit-perfect reconstruction (`encode -> decode` SHA-256 match).
- Better dedup under shifted edits using CDC.
- Binary seed portability and machine-readability (SBD1 container).
- Web3 transport via IPFS CLI publish/fetch.

## Non-Goals (This Iteration)
- Approximate search, generative synthesis, advanced delta encoding.
- On-chain registry, ENS mapping, storage deal management.
- End-to-end encryption defaults.

## Architecture
- `chunking.py`: deterministic `fixed`, `cdc_buzhash`, `cdc_rabin` chunkers.
- `storage.py`: pluggable storage interface, SQLite implementation for genome.
- `container.py`: SBD1 binary TLV serialization/parsing + integrity checks.
- `codec.py`: encode/decode/verify/prime workflows and genome snapshot/restore.
- `ipfs.py`: kubo HTTP RPC client for IPFS add/cat/pin operations.
- `ipfs_http.py`: thin kubo HTTP RPC wrapper over urllib.request.
- `cli.py`: Typer command surface.
- `ipfs_chunks.py`: individual chunk publish/fetch via kubo HTTP block API.
- `chunk_manifest.py`: chunk CID sidecar (`.sbd.chunks.json`) management.
- `hybrid_storage.py`: combined local SQLite + IPFS fallback storage.
- `cid.py`: CIDv1 deterministic computation from SHA-256 digest.
- `pinning.py`: remote pinning service integration (PSA).
- `oci.py`: OCI/ORAS artifact distribution bridge.
- `mlhooks.py`: MLflow and Hugging Face integration hooks.
- `errors.py`: exception hierarchy and error codes.
- `perf.py`: performance benchmarking and gate evaluation.
- `diagnostics.py`: runtime diagnostics and doctor checks.

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
- Optional seed signatures use HMAC-SHA256 in this iteration (`seedbraid sign` and `verify --require-signature`).
- Optional encryption uses SBE1 wrapper around SBD1 payload for backward-compatible rollout.
- SBE1 encryption wrapper uses versioned headers (v1 fixed scrypt params, v2 embedded
  params, v3 AEAD with algorithm identifier) to enable crypto evolution without
  breaking backward read compatibility.
- SBE1 v3 uses AES-256-GCM (NIST SP 800-38D) with HKDF-SHA256 key derivation,
  replacing the custom SHA-256 counter-mode cipher and external HMAC-SHA256 MAC.
  Requires optional `cryptography` package; falls back to v2 when unavailable.
- Optional `manifest-private` mode reduces metadata leakage at the cost of weaker post-restore provenance metadata.
- `seedbraid publish` warns on unencrypted seed publication to reduce accidental public leakage.
- IPFS fetch path includes retry/backoff and optional HTTP gateway fallback for resilience.
- `seedbraid pin-health` provides operator-visible local pin and block availability checks.
- `seedbraid doctor` provides preflight diagnostics for IPFS, genome path, and compression support.
- Error output is standardized with stable `SB_E_*` codes and next-action hints.
- Compatibility governance uses committed fixture seeds and regression tests as
  release gates; format evolution must preserve read compatibility or bump version.
- Performance governance adds benchmark gates for CDC reuse gain, seed-size ratio,
  and encode throughput (`scripts/bench_gate.py`).

## CI Integration Pack (SBD-ECO-001)
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
- CLI includes `seedbraid gen-encryption-key` for operator-safe generation of
  `SB_ENCRYPTION_KEY` secrets from command line workflows.

## Remote Pinning Adapter (SBD-ECO-002)
- Add provider-agnostic remote pin adapter interface for CID durability workflows.
- First provider implementation targets Pinning Services API-compatible endpoints.
- `seedbraid publish` can optionally trigger remote pin after local CID creation.
- CLI adds explicit remote-pin options for provider, endpoint/token, timeout, and retries.
- `seedbraid pin remote-add` allows pinning an existing CID without re-publishing seed bytes.
- Remote pin failures use dedicated `SB_E_*` operator codes with actionable hints.

## DVC Workflow Bridge (SBD-ECO-003)
- Add `examples/dvc/` as a minimal, script-driven DVC pipeline for
  `encode -> verify --strict -> fetch` Seedbraid seed workflows.
- DVC bridge is operational glue only. It does not change chunking, genome storage,
  SBD1/SBE1 serialization, or integrity semantics.
- Recommended pipeline artifact layout:
  - `artifacts/seed/current.sbd`: encoded seed tracked by DVC.
  - `artifacts/genome/snapshot.sgs`: reproducible genome snapshot for handoff/backup.
  - `artifacts/metadata/*`: sidecar metadata (`seed.cid`, `verify.ok`, digest files).
  - `artifacts/fetched/current.sbd`: fetched seed for downstream stages.
- Verify stage must call `seedbraid verify --strict` so integrity mismatch (or missing
  chunks) fails DVC reproduction early.
- Out of scope remains custom DVC plugin/registry integration.

## OCI/ORAS Artifact Distribution (SBD-ECO-004)
- Add ORAS bridge scripts for pushing/pulling Seedbraid seed artifacts via OCI
  registry references (`registry/repository:tag`).
- Define and document Seedbraid media/annotation conventions so registry metadata is
  machine-readable across providers:
  - artifact type: `application/vnd.seedbraid.seed.v1`
  - layer media type: `application/vnd.seedbraid.seed.layer.v1+sbd`
  - annotations: source SHA-256, chunker name, manifest-private flag.
- Push flow extracts manifest metadata from seed and writes OCI annotations.
- Pull flow restores the seed file from registry artifact payload without changing
  seed bytes; verification remains `seedbraid verify --strict`.
- Provider usage docs cover GHCR/ECR/GAR authentication entry points only.
- Out of scope remains provider-specific IAM automation.

## ML Tooling Hooks (SBD-ECO-005)
- Add optional MLflow logging script for registering Seedbraid seed metadata per run.
- Add optional Hugging Face upload script for seed file + metadata sidecar.
- Metadata model is intentionally minimal and reproducible:
  - seed filename + seed SHA-256
  - manifest-derived fields (source SHA, chunker, manifest-private flag)
  - optional transport pointers (CID / OCI reference)
- Restore workflow is documented from logged metadata:
  1. fetch referenced seed artifact,
  2. ensure required genome availability (or portable seed),
  3. run strict `seedbraid verify`,
  4. decode with encryption key only when seed is SBE1.
- Security caveat is explicit: avoid public leakage of provenance metadata unless
  seed is prepared with `--manifest-private` and access controls are appropriate.
- Out of scope remains managed production inference/deployment automation.

## IPFS Distributed Chunk Storage (SBD-ECO-006)
- Publish individual CDC chunks to IPFS as raw blocks via `ipfs block put
  --cid-codec raw`; reconstruct files by parallel-fetching chunks from IPFS.
- CIDv1 (raw codec, base32-lower) is computed deterministically from
  SHA-256 digest using stdlib only (`hashlib`, `base64`).
- Chunk CID metadata is stored in a JSON sidecar (`.sbd.chunks.json`);
  SBD1/SBE1 wire format is unchanged.
- `IPFSChunkStorage` implements the `GenomeStorage` Protocol backed by
  kubo HTTP RPC API calls (`/api/v0/block/put`, `/get`, `/stat`) with
  retry and exponential backoff.
- Parallel publish uses `ThreadPoolExecutor` (default 16 workers);
  parallel fetch is batched (default `batch_size=100`) to respect the
  streaming-first memory model.
- `HybridGenomeStorage` combines local `SQLiteGenome` with IPFS
  fallback; `cache_fetched` defaults to `True` at API level, storing
  remotely-fetched chunks into the local genome for subsequent reads
  (CLI `ipfs://` bare URI overrides to `False` for temporary cache).
- `seedbraid decode --genome ipfs://` activates `HybridGenomeStorage`
  automatically.  `ipfs://` alone uses a temporary cache (discarded
  after decode); `ipfs:///path/to/cache` persists fetched chunks to
  the specified directory for future reuse.
- CLI commands: `seedbraid publish-chunks` publishes all chunks referenced
  by a seed; `seedbraid fetch-decode` reconstructs the original file from
  IPFS.
- Chunk DAG pinning via IPFS MFS: `create_chunk_dag` builds a
  temporary MFS directory (`/seedbraid-chunks-<timestamp>`),
  copies all chunk CIDs into it, retrieves the directory root CID
  via `ipfs files stat --hash`, and removes the MFS entry in a
  `finally` block.  The DAG remains in the IPFS object store,
  pinnable via local `ipfs pin add` or remote PSA pin.
- IPFS operations use kubo HTTP RPC API (`/api/v0/`) via stdlib
  `urllib.request`; subprocess CLI calls are removed.  The API
  endpoint defaults to `http://127.0.0.1:5001/api/v0` and is
  configurable via `SB_KUBO_API` environment variable.
- `seedbraid doctor` checks kubo API reachability via
  `POST /api/v0/version` instead of `ipfs --version` CLI probe.
- Out of scope for this iteration: asyncio fetch, chunk-level encryption.

## Assumptions
- kubo daemon running (HTTP RPC API accessible at `SB_KUBO_API`,
  default `http://127.0.0.1:5001/api/v0`) when publish/fetch is used.
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
- Add `seedbraid genome snapshot` to export all stored chunks as `SGS1` binary snapshot.
- Add `seedbraid genome restore` to import chunk payloads into a target genome.
- Goal: operational DR workflow so non-portable seeds remain recoverable.
