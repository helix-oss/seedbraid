# Helix Ecosystem Tickets (Thread-Ready)

This file is the handoff packet for ecosystem expansion work in parallel threads.

Mandatory cross-thread rule:
- In any separate thread that implements ecosystem tickets, invoke and follow `$helix-dev` first.

Current baseline:
- Date: 2026-02-13
- Branch: `main`
- HEAD: `2cb8a78`
- Runtime target: Python `3.12+` (current local runtime may be newer)

## 1. Helix Technical Snapshot (Primal Info)

### 1.1 Product Core
- Purpose: reference-based reconstruction for large binaries with deterministic CDC.
- Lossless guarantee: `encode -> decode` must be bit-perfect (`sha256` match).
- Distribution model: compact seed + genome reuse; optional IPFS transport.

### 1.2 CLI Surface
- `helix encode`, `decode`, `verify`, `prime`
- `helix publish`, `fetch`, `pin-health`
- `helix doctor`, `sign`
- `helix genome snapshot|restore`
- Optional utilities: `export-genes`, `import-genes`

### 1.3 Format and Integrity
- HLX1 container (`docs/FORMAT.md`)
  - Sections: manifest, recipe, raw(optional), integrity, signature(optional)
- HLE1 wrapper for encrypted seeds
- Integrity checks: CRC32 + SHA-256 digests
- Optional signature: HMAC-SHA256

### 1.4 Storage and Chunking
- Genome storage: SQLite (`src/helix/storage.py`)
- Chunkers: `fixed`, `cdc_buzhash`, `cdc_rabin` (`src/helix/chunking.py`)
- Memory model: stream-first for encode/decode/prime paths

### 1.5 Ops and Quality
- Error code scheme: `HELIX_E_*` (`docs/ERROR_CODES.md`)
- Compatibility fixtures: `tests/fixtures/compat/v1/`
- Performance gates: `scripts/bench_gate.py` (`docs/PERFORMANCE.md`)
- OSS safety checklist: `docs/OSS_RELEASE_CHECKLIST.md`

## 2. Non-Negotiable Constraints
- Spec-first: update `docs/FORMAT.md` and `docs/DESIGN.md` before behavior/format changes.
- Determinism: same input + params -> same chunk boundaries.
- Bit-perfect in lossless paths.
- Keep test fixtures lightweight; avoid large binaries.
- Maintain backward-compatibility policy for HLX1.

## 3. Thread Startup Checklist
- Invoke `$helix-dev` first and keep it active for the thread.
- Run:
```bash
UV_CACHE_DIR=.uv-cache uv run --no-sync --no-editable ruff check .
PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run --no-sync --no-editable python -m pytest
```
- Read before coding:
  - `README.md`
  - `docs/FORMAT.md`
  - `docs/DESIGN.md`
  - `docs/ERROR_CODES.md`
  - `docs/PERFORMANCE.md`

## 4. Ticket Backlog

## [x] HLX-ECO-001 (P0) GitHub Actions Integration Pack
- Goal: provide CI-ready workflows for lint/test/compat/perf and optional publish.
- Scope:
  - Add `.github/workflows/ci.yml` for `ruff`, `python -m pytest`, compat tests.
  - Add workflow job for `scripts/bench_gate.py`.
  - Add optional manual workflow for seed publish (dry-run by default).
- Out of scope:
  - Cloud secret manager integration.
- Acceptance:
  - CI runs green on clean branch.
  - Bench gate can fail PR with clear message.
  - README has CI section with badge + local parity commands.
- Dependencies:
  - None.

## [x] HLX-ECO-002 (P0) IPFS Pinning Service Adapter
- Goal: improve CID durability beyond local node by integrating pinning API providers.
- Scope:
  - Add provider-agnostic pin adapter interface.
  - Implement one provider first (Pinning Services API-compatible).
  - Add `helix pin remote-add` or equivalent command.
  - Add retries/timeouts/error codes for remote pin requests.
- Out of scope:
  - Billing/subscription automation.
- Acceptance:
  - Seed publish can optionally trigger remote pin and report status.
  - Failure states map to explicit `HELIX_E_*` codes.
  - Tests include mocked API success/failure cases.
- Dependencies:
  - HLX-ECO-001 recommended (CI for network-mocked tests).

## [ ] HLX-ECO-003 (P1) DVC Workflow Bridge
- Goal: make Helix usable inside existing data/ML pipelines.
- Scope:
  - Provide integration recipe/scripts for DVC stages using Helix seeds.
  - Add `examples/dvc/` minimal pipeline with encode/verify/fetch flow.
  - Document recommended artifact layout (`seed`, `genome snapshot`, metadata).
- Out of scope:
  - Custom DVC plugin publishing to DVC registry.
- Acceptance:
  - Example DVC pipeline runs end-to-end locally.
  - README links to DVC integration section.
  - Verify step fails pipeline on integrity mismatch.
- Dependencies:
  - None.

## [ ] HLX-ECO-004 (P1) OCI/ORAS Artifact Distribution
- Goal: distribute HLX seeds through container registries.
- Scope:
  - Add script(s) for ORAS push/pull of `*.hlx` (media type defined).
  - Add metadata annotation convention (source sha, chunker, manifest_private flag).
  - Add docs for GHCR/ECR/GAR usage.
- Out of scope:
  - Registry-specific IAM automation.
- Acceptance:
  - Push seed to OCI registry and pull back losslessly.
  - Verify command succeeds after pull.
  - Clear troubleshooting notes for auth and media types.
- Dependencies:
  - HLX-ECO-001 recommended (workflow smoke job).

## [ ] HLX-ECO-005 (P2) ML Tooling Hooks (MLflow / Hugging Face)
- Goal: improve discoverability in ML artifact workflows.
- Scope:
  - Add optional script to register seed metadata into MLflow.
  - Add optional script to upload seed and sidecar metadata to Hugging Face Hub.
  - Document reproducible restore path from logged metadata.
- Out of scope:
  - Managed production inference deployment.
- Acceptance:
  - Scripted metadata push works with env-provided credentials.
  - Restore instructions from ML metadata are documented and tested.
  - Security caveats for public metadata are explicit.
- Dependencies:
  - HLX-ECO-001 recommended.

## 5. Ticket Template (Copy/Paste)
- Title: `[HLX-ECO-XXX] <short name>`
- Why: one paragraph business + technical rationale
- Scope: explicit included tasks
- Non-goals: explicit excluded tasks
- Acceptance criteria: objective pass/fail bullets
- Test plan: commands and expected outputs
- Rollout notes: migration/backward compatibility concerns

## 6. Suggested Execution Order
1. `[x] HLX-ECO-001`
2. `[x] HLX-ECO-002`
3. `[ ] HLX-ECO-003`
4. `[ ] HLX-ECO-004`
5. `[ ] HLX-ECO-005`

This order maximizes early reliability and gives later integrations a stable CI + ops foundation.
