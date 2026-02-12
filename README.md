# Helix v2

Helix v2 provides reference-based reconstruction with deterministic content-defined chunking (CDC), a binary HLX1 seed format, and IPFS publish/fetch transport.

## Features
- Lossless encode/decode with SHA-256 verification.
- Chunkers: `fixed`, `cdc_buzhash`, `cdc_rabin`.
- Genome storage (SQLite) for deduplicated chunk reuse.
- HLX1 binary seed container (`manifest + recipe + optional RAW + integrity`).
- IPFS CLI integration (`publish`, `fetch`).

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
```

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

## Tests and CI-Equivalent Local Commands
```bash
uv run --no-editable ruff check .
uv run --no-editable pytest
```

IPFS tests auto-skip when `ipfs` is not installed.

## 1-byte Insertion Dedup Benchmark
Run:
```bash
uv run --no-editable python scripts/bench_shifted_dedup.py
```

Expected behavior:
- `cdc_buzhash` should show better reuse than `fixed` when a single-byte insertion shifts offsets.

## Project Documents
- Format spec: `docs/FORMAT.md`
- Design rationale: `docs/DESIGN.md`
- Threat model: `docs/THREAT_MODEL.md`
- Plan: `PLANS.md`
