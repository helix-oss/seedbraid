# Seedbraid

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

Seedbraid is a reference-based reconstruction tool for large, similar binary artifacts.

It combines deterministic content-defined chunking (CDC), a compact binary `SBD1` seed format, reusable genome storage, and optional IPFS transport so you can ship reconstruction intent instead of repeatedly shipping full blobs.

## Why Seedbraid

Seedbraid is designed for workflows where ordinary file distribution becomes wasteful:

- large binary artifacts change often, but stay mostly similar
- fixed-size chunking loses reuse under shifted offsets
- you want compact transport plus bit-perfect restore guarantees
- you want one CLI surface for encode, verify, decode, publish, and fetch

In short: Seedbraid helps you move less data, reuse more content, and still verify exact reconstruction.

## When Seedbraid Is a Good Fit

Seedbraid works especially well for:

- large binary versioning: datasets, ML models, media assets, VM images
- distribution of many similar files across releases
- shift-heavy changes such as insertions that break fixed chunk reuse
- IPFS-based distribution and retrieval with integrity validation
- environments where transfer size, dedup reuse, and reproducibility matter

## Core Capabilities

- Lossless encode/decode with SHA-256 verification
- Deterministic chunking with `fixed`, `cdc_buzhash`, and `cdc_rabin`
- Genome storage backed by SQLite for deduplicated chunk reuse
- `SBD1` binary seed container with manifest, recipe, optional RAW, and integrity data
- IPFS publish/fetch transport
- Optional remote pin integration
- Strict verification mode for production-grade restore checks
- Optional signing and encryption support

## Installation

### pip
```bash
pip install seedbraid
```

### pipx
```bash
pipx install seedbraid
seedbraid --help
```

### uvx
```bash
uvx seedbraid --help
uvx seedbraid doctor
```

### Optional extras
```bash
# pip
pip install "seedbraid[zstd]"

# pipx
pipx install "seedbraid[zstd]"

# uvx
uvx --from "seedbraid[zstd]" seedbraid doctor
```

## Quick Start

### 1. Encode a file into a seed
```bash
seedbraid encode input.bin --genome ./genome --out seed.sbd --portable
```

### 2. Verify the seed
```bash
seedbraid verify seed.sbd --genome ./genome --strict
```

### 3. Decode the file back
```bash
seedbraid decode seed.sbd --genome ./genome --out recovered.bin
```

### 4. Compare the result
```bash
cmp -s input.bin recovered.bin && echo "bit-perfect roundtrip: OK"
```

> **Note:** If you installed via `uvx`, prefix commands with `uvx` (e.g. `uvx seedbraid encode ...`).
> For development builds, use `uv run --no-editable seedbraid` instead.

## Typical Workflow

A common Seedbraid workflow looks like this:

1. Prime or learn reusable chunks into a genome
2. Encode a target artifact into a compact `SBD1` seed
3. Verify integrity before distribution
4. Publish the seed if needed, including via IPFS
5. Fetch and decode later using the genome
6. Run strict verification when exact restore is required

## Beta Status

Seedbraid is currently in beta.

It is already useful for evaluation, benchmarking, and controlled workflows, but before production use you should validate behavior in your own runtime, storage, and network environment.

For production readiness, treat successful `verify --strict` and bit-perfect restore checks as release gates.

## Production Validation Checklist

Before using Seedbraid in CI/CD or production pipelines, run a strict smoke workflow like this:

```bash
uv sync --no-editable --extra dev

workdir="$(mktemp -d)"
python3 - <<'PY' "$workdir/input.bin"
from pathlib import Path
import sys

out = Path(sys.argv[1])
payload = (b"seedbraid-beta-smoke" * 20000) + bytes(range(256)) * 200
out.write_bytes(payload)
print(f"wrote {out} bytes={len(payload)}")
PY

uv run --no-sync --no-editable seedbraid encode "$workdir/input.bin" \
  --genome "$workdir/genome" \
  --out "$workdir/seed.sbd" \
  --chunker cdc_buzhash \
  --avg 65536 --min 16384 --max 262144 \
  --learn --portable --compression zlib

uv run --no-sync --no-editable seedbraid verify "$workdir/seed.sbd" \
  --genome "$workdir/genome" \
  --strict

uv run --no-sync --no-editable seedbraid decode "$workdir/seed.sbd" \
  --genome "$workdir/genome" \
  --out "$workdir/decoded.bin"

cmp -s "$workdir/input.bin" "$workdir/decoded.bin" \
  && echo "bit-perfect roundtrip: OK"
```

## CLI Reference

> All examples below use bare `seedbraid`. If you installed via `uvx`, prefix with `uvx`.
> For development builds, use `uv run --no-editable seedbraid`.

### Core Commands

#### Encode
```bash
seedbraid encode input.bin --genome ./genome --out seed.sbd

seedbraid encode input.bin --genome ./genome --out seed.sbd \
  --chunker cdc_buzhash --avg 65536 --min 16384 --max 262144 \
  --learn --no-portable --compression zlib

seedbraid encode input.bin --genome ./genome --out seed.private.sbd \
  --manifest-private

export SB_ENCRYPTION_KEY='your-secret-passphrase'
seedbraid encode input.bin --genome ./genome --out seed.encrypted.sbd \
  --encrypt --manifest-private
```

#### Decode
```bash
seedbraid decode seed.sbd --genome ./genome --out recovered.bin

seedbraid decode seed.encrypted.sbd --genome ./genome --out recovered.bin \
  --encryption-key "$SB_ENCRYPTION_KEY"
```

#### Verify
```bash
seedbraid verify seed.sbd --genome ./genome
seedbraid verify seed.sbd --genome ./genome --strict
seedbraid verify seed.sbd --genome ./genome --require-signature --signature-key "$SB_SIGNING_KEY"
seedbraid verify seed.encrypted.sbd --genome ./genome --strict \
  --encryption-key "$SB_ENCRYPTION_KEY"
```

`verify` supports two modes:

- Quick mode: checks seed integrity and required chunk availability
- Strict mode: reconstructs all content and enforces source size and SHA-256 match

#### Prime
```bash
seedbraid prime "./dataset/**/*" --genome ./genome --chunker cdc_buzhash
```

#### Doctor
```bash
seedbraid doctor --genome ./genome
```

`doctor` checks:

- Python runtime compatibility (`>=3.12`)
- IPFS CLI availability and version
- `IPFS_PATH` state
- genome path writability
- compression support (`zlib`, optional `zstd`)

### Advanced Commands

#### Genome Snapshot / Restore
```bash
seedbraid genome snapshot --genome ./genome --out genome.sgs
seedbraid genome restore genome.sgs --genome ./genome-dr --replace
```

#### Publish to IPFS
```bash
seedbraid publish seed.sbd --no-pin
seedbraid publish seed.sbd --pin
seedbraid publish seed.sbd --remote-pin \
  --remote-endpoint https://pin.example/api/v1 --remote-token "$SB_PINNING_TOKEN"
```

`publish` emits a warning when the seed is unencrypted. For sensitive data, prefer:

```bash
seedbraid encode --encrypt --manifest-private ...
```

When `--remote-pin` is enabled, Seedbraid also registers the CID with a configured Pinning Services API-compatible provider.

#### Fetch from IPFS
```bash
seedbraid fetch <cid> --out fetched.sbd
seedbraid fetch <cid> --out fetched.sbd --retries 5 --backoff-ms 300
seedbraid fetch <cid> --out fetched.sbd --gateway https://ipfs.io/ipfs
```

`fetch` retries `ipfs cat` with exponential backoff and can fall back to an HTTP gateway.

#### Pin Health
```bash
seedbraid pin-health <cid>
```

#### Remote Pin Add
```bash
export SB_PINNING_ENDPOINT='https://pin.example/api/v1'
export SB_PINNING_TOKEN='your-api-token'
seedbraid pin remote-add <cid>
```

#### Sign Seed
```bash
export SB_SIGNING_KEY='your-shared-secret'
seedbraid sign seed.sbd --out seed.signed.sbd --key-env SB_SIGNING_KEY --key-id team-a
```

#### Export / Import Genes
```bash
seedbraid export-genes seed.sbd --genome ./genome --out genes.pack
seedbraid import-genes genes.pack --genome ./another-genome
```

## Generate an Encryption Key

Generate a high-entropy key for `SB_ENCRYPTION_KEY`:

```bash
seedbraid gen-encryption-key
```

Print shell export format:

```bash
seedbraid gen-encryption-key --shell
```

Set the current shell variable directly:

```bash
eval "$(seedbraid gen-encryption-key --shell)"
```

## IPFS Setup

Check whether the IPFS CLI is available:

```bash
ipfs --version
```

If missing, install Kubo and ensure `ipfs` is available on your `PATH`.

## Common Failures

- `ipfs CLI not found`
  - Install IPFS and confirm with `ipfs --version`
- `Missing required chunk` on decode or verify
  - Provide the correct `--genome`, or re-encode with `--portable`
- `zstd` compression error
  - Install optional dependency `zstandard`, or use `--compression zlib`

## Troubleshooting Matrix

| Symptom | Error Code | Next Action |
|---|---|---|
| Encryption requested but key missing | `SB_E_ENCRYPTION_KEY_MISSING` | Pass `--encryption-key` or set `SB_ENCRYPTION_KEY`. |
| Signing requested but key missing | `SB_E_SIGNING_KEY_MISSING` | Export signing key env var and retry `seedbraid sign`. |
| IPFS CLI missing | `SB_E_IPFS_NOT_FOUND` | Install Kubo and confirm `ipfs --version`. |
| IPFS fetch/publish failure | `SB_E_IPFS_FETCH` / `SB_E_IPFS_PUBLISH` | Check daemon/network, retry, use gateway fallback if needed. |
| Remote pin configuration missing | `SB_E_REMOTE_PIN_CONFIG` | Set endpoint/token env vars or pass options. |
| Remote pin auth failed | `SB_E_REMOTE_PIN_AUTH` | Verify provider token permissions and retry. |
| Remote pin request invalid | `SB_E_REMOTE_PIN_REQUEST` | Check CID/provider options and retry. |
| Remote pin timeout/failure | `SB_E_REMOTE_PIN_TIMEOUT` / `SB_E_REMOTE_PIN` | Increase retries/timeout or check provider health. |
| Seed parse/integrity failure | `SB_E_SEED_FORMAT` | Re-fetch/rebuild seed and verify source integrity. |

---

# Development & Contributing

The sections below are for contributors and developers working on Seedbraid itself.

## Development Setup

```bash
uv sync --no-editable --extra dev
```

Optional zstd support:

```bash
uv sync --no-editable --extra dev --extra zstd
```

Refresh the lockfile after dependency changes:

```bash
uv lock
```

## Local Checks

```bash
uv run --no-editable ruff check .
uv run --no-editable python -m pytest
uv run --no-editable python -m pytest tests/test_compat_fixtures.py
```

IPFS tests auto-skip when `ipfs` is not installed.

Compatibility fixtures are stored in `tests/fixtures/compat/v1/` and validated by `tests/test_compat_fixtures.py`.

To regenerate them intentionally:

```bash
uv run --no-editable python scripts/gen_compat_fixtures.py
```

## CI

GitHub Actions workflows:

- `.github/workflows/ci.yml`
  - `ruff check .`
  - `python -m pytest`
  - compatibility fixtures validation
  - benchmark gate
- `.github/workflows/publish-seed.yml`
  - manual only, `dry_run=true` by default
  - generates a seed from `source_path`
  - runs `seedbraid verify --strict`
  - publishes to IPFS only when `dry_run=false`
  - installs Kubo when needed
  - verifies Kubo release signature status and checksum
  - supports `pin`, `portable`, `manifest_private`, and optional `encrypt`

Local parity commands:

```bash
uv sync --no-editable --extra dev
uv run --no-sync --no-editable ruff check .
PYTHONPATH=src uv run --no-sync --no-editable python -m pytest
PYTHONPATH=src uv run --no-sync --no-editable python -m pytest tests/test_compat_fixtures.py
uv run --no-sync --no-editable python scripts/bench_gate.py \
  --min-reuse-improvement-bps 1 \
  --max-seed-size-ratio 1.20 \
  --min-cdc-throughput-mib-s 0.10 \
  --json-out .artifacts/bench-report.json
```

## Benchmarking

### 1-byte insertion dedup benchmark
```bash
uv run --no-editable python scripts/bench_shifted_dedup.py
uv run --no-editable python scripts/bench_gate.py \
  --min-reuse-improvement-bps 1 \
  --max-seed-size-ratio 1.20 \
  --min-cdc-throughput-mib-s 0.10 \
  --json-out .artifacts/bench-report.json
```

Expected behavior:

- `cdc_buzhash` should show better reuse than `fixed` when a single-byte insertion shifts offsets
- `bench_gate.py` exits non-zero when configured thresholds are violated

## Integrations

### DVC Integration
- Minimal DVC bridge lives in `examples/dvc/`
- Pipeline stages are `encode -> verify --strict -> fetch`
- The integration recipe and artifact layout are documented in `examples/dvc/README.md`

### OCI Integration
- ORAS bridge scripts and usage docs live in `examples/oci/`
- Default OCI metadata convention:
  - artifact type: `application/vnd.seedbraid.seed.v1`
  - layer media type: `application/vnd.seedbraid.seed.layer.v1+sbd`
  - annotations: source SHA-256, chunker, manifest-private flag, seed title
- Push/pull scripts:
  - `examples/oci/scripts/push_seed.sh <seed.sbd> <registry/repository:tag>`
  - `examples/oci/scripts/pull_seed.sh <registry/repository:tag> <out.sbd>`
- After pull, run strict verification:
  - `seedbraid verify <out.sbd> --genome <genome-path> --strict`

### ML Tooling Hooks
- Scripts for MLflow metadata logging and Hugging Face upload live in `examples/ml/`
- MLflow hook logs seed metadata fields
- Hugging Face hook uploads `seed.sbd` and a metadata sidecar
- Restore workflow is documented in `examples/ml/README.md`

## Roadmap

Current adoption priorities include:

- a faster onboarding path
- stronger benchmark evidence versus alternatives
- security and operator tooling such as signing, encryption, `doctor`, `snapshot`, and `restore`
- stable format governance and backward-compatibility policy for long-lived seed archives

## Project Documents

- Format spec: `docs/FORMAT.md`
- Design rationale: `docs/DESIGN.md`
- Threat model: `docs/THREAT_MODEL.md`
- Error codes: `docs/ERROR_CODES.md`
- Performance gates: `docs/PERFORMANCE.md`
- DVC example: `examples/dvc/README.md`
- OCI example: `examples/oci/README.md`
- ML tooling example: `examples/ml/README.md`

## Support Seedbraid

Seedbraid is maintained as an open-source project.

If Seedbraid helps your workflow, please consider supporting the project through the repository `Sponsor` button. Support goes directly toward maintenance, documentation, and compatibility/performance validation.

## Open Source Governance

- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
