# Helix v2

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

Helix v2 provides reference-based reconstruction with deterministic content-defined chunking (CDC), a binary HLX1 seed format, and IPFS publish/fetch transport.

## Features
- Lossless encode/decode with SHA-256 verification.
- Chunkers: `fixed`, `cdc_buzhash`, `cdc_rabin`.
- Genome storage (SQLite) for deduplicated chunk reuse.
- HLX1 binary seed container (`manifest + recipe + optional RAW + integrity`).
- IPFS CLI integration (`publish`, `fetch`).

## Why Helix
- Seed-first architecture: reconstruction intent is shipped as a compact `HLX1` seed (`manifest + recipe`) instead of shipping full blobs repeatedly.
- End-to-end integrity posture: strict verify mode, compatibility fixtures, and performance gates are built into the project workflow.
- Practical Web3 distribution: CID publish/fetch is part of the same CLI surface as encode/decode, reducing operational handoffs.
- Shift-resilient dedup by default: CDC is first-class and benchmarked against fixed chunking with reproducible scripts.

## Best-Fit Use Cases
- Large binary versioning: datasets, ML models, media assets, and VM images.
- Distribution of many similar files: share a common genome and distribute compact seeds.
- IPFS-based distribution and retrieval: distribute by CID and verify reconstruction integrity.
- Shift-heavy changes (for example, single-byte insertion): CDC improves reuse over fixed chunking.

## What It Takes for OSS Adoption
- A 5-minute onboarding path (installation + first encode/decode tutorial).
- Benchmark evidence that Helix wins against alternatives on size, transfer time, and restore speed.
- Security and operations readiness: signing/encryption and operator tooling (`doctor`, `snapshot`, `restore`).
- Stable format governance and backward-compatibility policy for long-lived seed archives.

## Quick Start
```bash
uv sync --no-editable --extra dev
```

Optional zstd support:
```bash
uv sync --no-editable --extra dev --extra zstd
```

Refresh lockfile after dependency changes:
```bash
uv lock
```

## CLI
### Encode
```bash
uv run --no-editable helix encode input.bin --genome ./genome --out seed.hlx \
  --chunker cdc_buzhash --avg 65536 --min 16384 --max 262144 \
  --learn --no-portable --compression zlib

uv run --no-editable helix encode input.bin --genome ./genome --out seed.private.hlx \
  --manifest-private

export HELIX_ENCRYPTION_KEY='your-secret-passphrase'
uv run --no-editable helix encode input.bin --genome ./genome --out seed.encrypted.hlx \
  --encrypt --manifest-private
```

### Decode
```bash
uv run --no-editable helix decode seed.hlx --genome ./genome --out recovered.bin
uv run --no-editable helix decode seed.encrypted.hlx --genome ./genome --out recovered.bin \
  --encryption-key "$HELIX_ENCRYPTION_KEY"
```

### Verify
```bash
uv run --no-editable helix verify seed.hlx --genome ./genome
uv run --no-editable helix verify seed.hlx --genome ./genome --strict
uv run --no-editable helix verify seed.hlx --genome ./genome --require-signature --signature-key "$HELIX_SIGNING_KEY"
uv run --no-editable helix verify seed.encrypted.hlx --genome ./genome --strict \
  --encryption-key "$HELIX_ENCRYPTION_KEY"
```

`verify` supports two modes:
- Quick mode (default): checks seed integrity and required chunk availability.
- Strict mode (`--strict`): reconstructs all content and enforces source size and SHA-256 match.

### Prime
```bash
uv run --no-editable helix prime "./dataset/**/*" --genome ./genome --chunker cdc_buzhash
```

### Genome Snapshot / Restore
```bash
uv run --no-editable helix genome snapshot --genome ./genome --out genome.hgs
uv run --no-editable helix genome restore genome.hgs --genome ./genome-dr --replace
```

### Publish (IPFS)
```bash
uv run --no-editable helix publish seed.hlx --no-pin
uv run --no-editable helix publish seed.hlx --pin
```

`publish` emits a warning when seed is unencrypted. For sensitive data, prefer:
`helix encode --encrypt --manifest-private ...` before publishing.

### Fetch (IPFS)
```bash
uv run --no-editable helix fetch <cid> --out fetched.hlx
uv run --no-editable helix fetch <cid> --out fetched.hlx --retries 5 --backoff-ms 300
uv run --no-editable helix fetch <cid> --out fetched.hlx --gateway https://ipfs.io/ipfs
```

`fetch` retries `ipfs cat` with exponential backoff and can fallback to an HTTP gateway.

### Pin Health (IPFS)
```bash
uv run --no-editable helix pin-health <cid>
```

### Doctor
```bash
uv run --no-editable helix doctor --genome ./genome
```

`doctor` checks:
- Python runtime compatibility (>=3.12)
- IPFS CLI availability/version
- `IPFS_PATH` state
- genome path writability
- compression support (`zlib`, optional `zstd`)

### Sign Seed (optional)
```bash
export HELIX_SIGNING_KEY='your-shared-secret'
uv run --no-editable helix sign seed.hlx --out seed.signed.hlx --key-env HELIX_SIGNING_KEY --key-id team-a
```

### Export / Import Genes (optional)
```bash
uv run --no-editable helix export-genes seed.hlx --genome ./genome --out genes.pack
uv run --no-editable helix import-genes genes.pack --genome ./another-genome
```

## IPFS Installation/Check
Check if IPFS CLI is available:
```bash
ipfs --version
```

If missing, install Kubo (IPFS CLI) and ensure `ipfs` is on your PATH.

## Common Failures
- `ipfs CLI not found`:
  - Install IPFS and verify with `ipfs --version`.
- `Missing required chunk` on decode/verify:
  - Provide the correct `--genome`, or re-encode with `--portable`.
- `zstd` compression error:
  - Install optional dependency `zstandard`, or use `--compression zlib`.

## Troubleshooting Matrix
| Symptom | Error Code | Next Action |
|---|---|---|
| Encryption requested but key missing | `HELIX_E_ENCRYPTION_KEY_MISSING` | Pass `--encryption-key` or set `HELIX_ENCRYPTION_KEY`. |
| Signing requested but key missing | `HELIX_E_SIGNING_KEY_MISSING` | Export signing key env var and retry `helix sign`. |
| IPFS CLI missing | `HELIX_E_IPFS_NOT_FOUND` | Install Kubo and confirm `ipfs --version`. |
| IPFS fetch/publish failure | `HELIX_E_IPFS_FETCH` / `HELIX_E_IPFS_PUBLISH` | Check daemon/network, retry, use gateway fallback if needed. |
| Seed parse/integrity failure | `HELIX_E_SEED_FORMAT` | Re-fetch/rebuild seed and verify source integrity. |

## CI (HLX-ECO-001)
GitHub Actions workflows:
- `.github/workflows/ci.yml`
  - Lint: `ruff check .`
  - Test: `pytest`
  - Compatibility fixtures: `pytest tests/test_compat_fixtures.py`
  - Benchmark gate: `python scripts/bench_gate.py ...`
- `.github/workflows/publish-seed.yml` (manual only, `dry_run=true` default)

Local parity commands:
```bash
uv sync --no-editable --extra dev
uv run --no-sync --no-editable ruff check .
PYTHONPATH=src uv run --no-sync --no-editable pytest
PYTHONPATH=src uv run --no-sync --no-editable pytest tests/test_compat_fixtures.py
uv run --no-sync --no-editable python scripts/bench_gate.py \
  --min-reuse-improvement-bps 1 \
  --max-seed-size-ratio 1.20 \
  --min-cdc-throughput-mib-s 0.10 \
  --json-out .artifacts/bench-report.json
```

## Tests and CI-Equivalent Local Commands
```bash
uv run --no-editable ruff check .
uv run --no-editable pytest
uv run --no-editable pytest tests/test_compat_fixtures.py
```

IPFS tests auto-skip when `ipfs` is not installed.
Compatibility fixtures are stored in `tests/fixtures/compat/v1/` and are
validated by `tests/test_compat_fixtures.py`.
Regenerate intentionally with:
`uv run --no-editable python scripts/gen_compat_fixtures.py`.

## 1-byte Insertion Dedup Benchmark
Run:
```bash
uv run --no-editable python scripts/bench_shifted_dedup.py
uv run --no-editable python scripts/bench_gate.py \
  --min-reuse-improvement-bps 1 \
  --max-seed-size-ratio 1.20 \
  --min-cdc-throughput-mib-s 0.10 \
  --json-out .artifacts/bench-report.json
```

Expected behavior:
- `cdc_buzhash` should show better reuse than `fixed` when a single-byte insertion shifts offsets.
- `bench_gate.py` exits non-zero when configured thresholds are violated.

## Project Documents
- Format spec: `docs/FORMAT.md`
- Design rationale: `docs/DESIGN.md`
- Threat model: `docs/THREAT_MODEL.md`
- Error codes: `docs/ERROR_CODES.md`
- Performance gates: `docs/PERFORMANCE.md`
- Ecosystem integration tickets: `docs/ECOSYSTEM_TICKETS.md`
- Product packaging/pricing draft: `docs/PRODUCT_PACKAGING_PRICING.md`
- OSS release checklist: `docs/OSS_RELEASE_CHECKLIST.md`
- Plan: `PLANS.md`

## Open Source Governance
- License: `MIT` (`/Users/kytk/Documents/New project/LICENSE`)
- Security policy: `/Users/kytk/Documents/New project/SECURITY.md`
- Contributing guide: `/Users/kytk/Documents/New project/CONTRIBUTING.md`
