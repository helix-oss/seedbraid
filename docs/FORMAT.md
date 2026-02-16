# HLX1 Seed Container Format

## Overview
HLX1 is a binary seed container used by Helix. It stores:
- manifest metadata (JSON)
- binary reconstruction recipe
- optional RAW payloads (portable mode)
- integrity metadata

The DNA-style ACGT representation is debug-only and out of scope for container storage.

## Binary Layout
- Header:
  - magic: 4 bytes, ASCII `HLX1`
  - version: uint16 big-endian (`1`)
  - section_count: uint16 big-endian
- Sections (`section_count` entries):
  - type: uint16 big-endian
  - length: uint64 big-endian
  - value: `length` bytes

## Section Types
- `1` Manifest
- `2` Recipe
- `3` RAW payload table (optional)
- `4` Integrity
- `5` Signature (optional)

Unknown section types are ignored by current parser only if integrity is still verifiable.

## Manifest Section (Type 1)
Payload format:
- compression_id: uint8
- compressed_manifest_bytes: bytes

Compression IDs:
- `0`: none
- `1`: zlib
- `2`: zstd

Manifest JSON fields (v1 baseline):
- `format`: `"HLX1"`
- `version`: `1`
- `source_size`: int
- `source_sha256`: hex string
- `chunker`: `{name,min,avg,max,window_size}`
- `portable`: bool
- `learn`: bool
- `stats`: `{total_chunks,reused_chunks,new_chunks,raw_chunks}`
- `created_at`: RFC3339 UTC string

Private manifest mode (`--manifest-private`):
- `manifest_private`: `true`
- `source_size`: `null`
- `source_sha256`: `null`
- `created_at`: omitted
- `stats`: omitted
- `chunker`: may be reduced to `{"name": ...}` only
- Purpose: reduce metadata leakage when publishing/distributing seeds.

## Recipe Section (Type 2)
Binary recipe encodes deterministic reconstruction operations.

Payload format:
- `op_count`: uint32
- `hash_count`: uint32
- `hash_table`: `hash_count * 32` bytes (SHA-256 digest table)
- `ops`: repeated `op_count` times:
  - `opcode`: uint8 (`1`=REF, `2`=RAW)
  - `hash_index`: uint32

Semantics:
- `REF(hash_index)`: retrieve chunk by hash from genome; fallback to RAW table if present.
- `RAW(hash_index)`: retrieve chunk from RAW table; fallback to genome if missing.

## RAW Section (Type 3, optional)
Payload format:
- `count`: uint32
- repeated `count` times:
  - `hash_index`: uint32
  - `size`: uint32
  - `chunk_bytes`: `size` bytes

Used for portable seeds to carry unknown chunk payloads.

## Integrity Section (Type 4)
UTF-8 JSON with:
- `manifest_crc32`: int (crc32 over entire Manifest section payload)
- `recipe_crc32`: int (crc32 over Recipe section payload)
- `payload_crc32`: int (crc32 over container bytes from start through end of last non-integrity section)
- `manifest_sha256`: hex string (sha256 over Manifest section payload)
- `recipe_sha256`: hex string (sha256 over Recipe section payload)
- `payload_sha256`: hex string (sha256 over container bytes from start through end of last non-integrity section)
- `raw_crc32` / `raw_sha256`: optional, present when RAW section exists

## Signature Section (Type 5, optional)
UTF-8 JSON with:
- `algorithm`: `"hmac-sha256"`
- `key_id`: string
- `signed_payload_sha256`: hex string
- `signature`: hex string (HMAC-SHA256 over signed payload)

Signed payload definition:
- bytes from start of file through end of last non-signature/non-integrity section.
- Signature section must appear before integrity section.

## Decode/Verify Requirements
- Parser must validate magic/version and integrity section.
- For lossless mode, decode output SHA-256 must equal `manifest.source_sha256`.
- Verify must report missing required chunk hashes when genome/raw are insufficient.

## IPFS Remote Pinning (Operational, No Wire-Format Change)
- HLX-ECO-002 adds remote pin operations for published CIDs via provider adapters.
- Remote pin integration is operational metadata only and does not modify HLX1/HLE1
  bytes, section layout, or integrity/signature semantics.
- `helix publish` may optionally trigger remote pin registration after CID creation.
- `helix pin remote-add` (or equivalent) may register an existing CID with a remote
  pinning provider.

## DVC Workflow Bridge (Operational, No Wire-Format Change)
- HLX-ECO-003 adds DVC integration recipes/scripts under `examples/dvc/` for
  `encode -> verify -> fetch` workflows.
- The bridge reuses existing artifact formats only:
  - seed: `*.hlx` (`HLX1`/`HLE1`)
  - genome snapshot: `*.hgs` (`HGS1`)
  - metadata sidecars: UTF-8 text/JSON files (for example CID and verify marker)
- DVC tracking metadata does not modify seed/genome bytes.
- Integrity enforcement remains `helix verify --strict`; verification failure is
  expected to fail the corresponding pipeline stage.

## OCI/ORAS Artifact Distribution (Operational, No Wire-Format Change)
- HLX-ECO-004 adds ORAS push/pull scripts for distributing `*.hlx` seeds through
  OCI registries.
- Distribution uses OCI transport metadata only; HLX1/HLE1 bytes are unchanged.
- Defined media/metadata conventions:
  - OCI artifact type: `application/vnd.helix.seed.v1`
  - seed layer media type: `application/vnd.helix.seed.layer.v1+hlx`
  - annotations:
    - `io.helix.seed.source-sha256`
    - `io.helix.seed.chunker`
    - `io.helix.seed.manifest-private`
    - `org.opencontainers.image.title`
- Annotation values come from seed manifest fields and are serialized as strings.
- `oras push`/`oras pull` must preserve seed bytes exactly; post-pull integrity is
  enforced by running `helix verify` against the pulled seed.

## ML Tooling Hooks (Operational, No Wire-Format Change)
- HLX-ECO-005 adds optional scripts for logging Helix seed metadata to MLflow and
  uploading seed + metadata sidecars to Hugging Face Hub.
- Added metadata is sidecar JSON only and does not mutate HLX1/HLE1 bytes.
- Sidecar metadata is derived from seed manifest + seed file digest and may include
  optional transport pointers (for example IPFS CID or OCI reference).
- Reproducible restore still depends on `helix verify --strict` using:
  - retrieved seed bytes
  - matching genome path (or portable RAW coverage)
  - optional encryption key for HLE1 seeds
- Security requirement: metadata can expose provenance fields (`source_sha256`,
  chunker profile, transport references); public uploads should use
  `--manifest-private` and encrypted seeds when needed.

## Versioning
- Backward-incompatible changes require `version` increment and docs update.
- New optional sections may be added via TLV without changing version.

## Compatibility Policy
- Helix keeps fixture seeds under `tests/fixtures/compat/v1/` as the canonical
  compatibility corpus for HLX1 v1.
- CI must parse and strictly verify these fixtures on every change.
- Repository CI baseline is defined in `.github/workflows/ci.yml` and includes
  lint (`ruff check .`), full tests (`python -m pytest`), fixture compatibility
  tests (`python -m pytest tests/test_compat_fixtures.py`), and benchmark gates.
- Optional publish workflow (`.github/workflows/publish-seed.yml`) is manual and
  runs `helix encode` + strict `helix verify` before optional IPFS publish
  (`dry_run=true` by default) to prevent publishing unverified seeds.
- In real publish mode, workflow verifies upstream Kubo release tag signature
  (GitHub verification API) and archive checksum before installing `ipfs` CLI.
- Any change that breaks fixture parsing/verification is considered breaking and
  must follow all of:
  1. bump container version,
  2. add migration path/command,
  3. preserve old-version read support or document explicit deprecation window,
  4. add new version fixtures without deleting old fixtures.
- Fixture regeneration is allowed only when behavior change is intentional and
  the compatibility policy above is followed.

## Encrypted Seed Wrapper (HLE1)
For optional at-rest encryption, Helix wraps HLX1 bytes in `HLE1` format.

Binary layout:
- magic: 4 bytes, ASCII `HLE1`
- version: uint16 (`1`)
- salt_len: uint8 (`16`)
- nonce_len: uint8 (`16`)
- ciphertext_len: uint64
- salt: `salt_len` bytes
- nonce: `nonce_len` bytes
- ciphertext: `ciphertext_len` bytes
- mac: 32 bytes (`HMAC-SHA256`)

Semantics:
- Plain HLX1 payload is encrypted with a key derived from passphrase + salt.
- MAC is validated before decryption output is accepted.
- On MAC failure, parser must fail with explicit tamper/wrong-key error.
- Helix CLI provides `helix gen-encryption-key` to generate a high-entropy
  passphrase for `HELIX_ENCRYPTION_KEY` usage; this helper does not change
  HLE1 wire format.
- Existing unencrypted HLX1 files remain valid and unchanged.

## Genes Pack (Optional Utility Format)
For `helix export-genes` / `helix import-genes`, Helix defines a small sidecar binary format:
- magic: 5 bytes, ASCII `GENE1`
- count: uint32
- repeated `count` times:
  - hash: 32 bytes (sha256)
  - size: uint32
  - payload: `size` bytes

If `size == 0`, payload is absent (export side could not find this chunk in genome).

## Genome Snapshot Format (HGS1)
For `helix genome snapshot` / `helix genome restore`, Helix defines a binary snapshot format:
- magic: 4 bytes, ASCII `HGS1`
- version: uint16 (`1`)
- chunk_count: uint64
- repeated `chunk_count` times:
  - hash: 32 bytes (sha256)
  - size: uint32
  - payload: `size` bytes

Semantics:
- Snapshot contains full chunk payloads from the selected genome database.
- Restore may merge into existing genome or replace it (CLI option).
- Invalid/truncated snapshot must fail with actionable error messages.
