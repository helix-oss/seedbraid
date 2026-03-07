# Helix

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

Helix provides reference-based reconstruction with deterministic content-defined chunking (CDC), a binary HLX1 seed format, and IPFS publish/fetch transport.

## Beta Status (Read First)
- Helix is currently in beta stage.
- Before production use, run strict validation in your own runtime/storage/network environment.
- Treat successful `verify --strict` and bit-perfect restore checks as release gates for your team.

## Strict Validation Workflow (Required Before Production)
Run the following smoke workflow before relying on Helix in CI/CD or production pipelines:

```bash
uv sync --no-editable --extra dev

workdir="$(mktemp -d)"
python3 - <<'PY' "$workdir/input.bin"
from pathlib import Path
import sys

out = Path(sys.argv[1])
payload = (b"helix-beta-smoke" * 20000) + bytes(range(256)) * 200
out.write_bytes(payload)
print(f"wrote {out} bytes={len(payload)}")
PY

uv run --no-sync --no-editable helix encode "$workdir/input.bin" \
  --genome "$workdir/genome" \
  --out "$workdir/seed.hlx" \
  --chunker cdc_buzhash \
  --avg 65536 --min 16384 --max 262144 \
  --learn --portable --compression zlib

uv run --no-sync --no-editable helix verify "$workdir/seed.hlx" \
  --genome "$workdir/genome" \
  --strict

uv run --no-sync --no-editable helix decode "$workdir/seed.hlx" \
  --genome "$workdir/genome" \
  --out "$workdir/decoded.bin"

cmp -s "$workdir/input.bin" "$workdir/decoded.bin" \
  && echo "bit-perfect roundtrip: OK"

UV_CACHE_DIR=.uv-cache uv run --no-sync --no-editable ruff check .
PYTHONPATH=src UV_CACHE_DIR=.uv-cache uv run --no-sync --no-editable python -m pytest
```

## Features
- Lossless encode/decode with SHA-256 verification.
- Chunkers: `fixed`, `cdc_buzhash`, `cdc_rabin`.
- Genome storage (SQLite) for deduplicated chunk reuse.
- HLX1 binary seed container (`manifest + recipe + optional RAW + integrity`).
- IPFS CLI integration (`publish`, `fetch`).
- Optional remote pin integration (`pin remote-add`, publish-time remote pin).

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

## Installation

> **Note**: PyPI publishing is currently on hold. `pip install helix` is not yet available.
> Please install from source.

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

## Generate Encryption Key
Generate a high-entropy key for `HELIX_ENCRYPTION_KEY`:
```bash
uv run --no-editable helix gen-encryption-key
```

Print shell export format:
```bash
uv run --no-editable helix gen-encryption-key --shell
```

Set current shell variable directly:
```bash
eval "$(uv run --no-editable helix gen-encryption-key --shell)"
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
uv run --no-editable helix publish seed.hlx --remote-pin \
  --remote-endpoint https://pin.example/api/v1 --remote-token "$HELIX_PINNING_TOKEN"
```

`publish` emits a warning when seed is unencrypted. For sensitive data, prefer:
`helix encode --encrypt --manifest-private ...` before publishing.
When `--remote-pin` is enabled, Helix also registers CID with configured remote
pin provider (Pinning Services API-compatible).

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

### Remote Pin Add (IPFS)
```bash
export HELIX_PINNING_ENDPOINT='https://pin.example/api/v1'
export HELIX_PINNING_TOKEN='your-api-token'
uv run --no-editable helix pin remote-add <cid>
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
| Remote pin configuration missing | `HELIX_E_REMOTE_PIN_CONFIG` | Set endpoint/token env vars or pass options. |
| Remote pin auth failed | `HELIX_E_REMOTE_PIN_AUTH` | Verify provider token permissions and retry. |
| Remote pin request invalid | `HELIX_E_REMOTE_PIN_REQUEST` | Check CID/provider options and retry. |
| Remote pin timeout/failure | `HELIX_E_REMOTE_PIN_TIMEOUT` / `HELIX_E_REMOTE_PIN` | Increase retries/timeout or check provider health. |
| Seed parse/integrity failure | `HELIX_E_SEED_FORMAT` | Re-fetch/rebuild seed and verify source integrity. |

## CI (HLX-ECO-001)
GitHub Actions workflows:
- `.github/workflows/ci.yml`
  - Lint: `ruff check .`
  - Test: `python -m pytest`
  - Compatibility fixtures: `python -m pytest tests/test_compat_fixtures.py`
  - Benchmark gate: `python scripts/bench_gate.py ...`
- `.github/workflows/publish-seed.yml` (manual only, `dry_run=true` default)
  - Generates seed from `source_path` via `helix encode`
  - Runs strict integrity check via `helix verify --strict`
  - Publishes to IPFS only when `dry_run=false`
  - Installs Kubo (`ipfs` CLI) on runner when `dry_run=false` (version configurable via `kubo_version`)
  - Verifies Kubo release tag signature status via GitHub API before install
  - Verifies downloaded Kubo archive checksum (`sha512`) before extraction
  - Supports `pin`, `portable`, `manifest_private`, and optional `encrypt`
    (`HELIX_ENCRYPTION_KEY` secret required when `encrypt=true`)

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

## DVC Integration (HLX-ECO-003)
- Minimal DVC bridge lives in `examples/dvc/`.
- Pipeline stages are `encode -> verify --strict -> fetch`.
- `verify` stage is strict and must fail pipeline reproduction on integrity mismatch.
- Integration recipe and artifact layout are documented in `examples/dvc/README.md`.

## OCI Integration (HLX-ECO-004)
- ORAS bridge scripts and usage docs live in `examples/oci/`.
- Default OCI metadata convention:
  - artifact type: `application/vnd.helix.seed.v1`
  - layer media type: `application/vnd.helix.seed.layer.v1+hlx`
  - annotations: source SHA-256, chunker, manifest-private flag, seed title
- Push/pull scripts:
  - `examples/oci/scripts/push_seed.sh <seed.hlx> <registry/repository:tag>`
  - `examples/oci/scripts/pull_seed.sh <registry/repository:tag> <out.hlx>`
- After pull, run strict verification:
  - `helix verify <out.hlx> --genome <genome-path> --strict`

## ML Tooling Hooks (HLX-ECO-005)
- Scripts for MLflow metadata logging and Hugging Face upload live in `examples/ml/`.
- MLflow hook logs seed metadata fields (seed digest, manifest provenance, optional transport refs).
- Hugging Face hook uploads `seed.hlx` + metadata sidecar with env-provided token credentials.
- Restore workflow from logged metadata is documented in `examples/ml/README.md`.

## Tests and CI-Equivalent Local Commands
```bash
uv run --no-editable ruff check .
uv run --no-editable python -m pytest
uv run --no-editable python -m pytest tests/test_compat_fixtures.py
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
- DVC workflow bridge example: `examples/dvc/README.md`
- OCI/ORAS distribution example: `examples/oci/README.md`
- ML tooling hooks example: `examples/ml/README.md`
- OSS release checklist: `docs/OSS_RELEASE_CHECKLIST.md`
- Plan: `PLANS.md`

## Support Helix
- Helix is maintained as an open-source project.
- If Helix helps your workflow, please consider donating via the repository `Sponsor` button.
- Donations directly support maintenance, documentation, and compatibility/performance validation.

## Open Source Governance
- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
