# SBD1 Seed Container Format

## Overview
SBD1 is a binary seed container used by Seedbraid. It stores:
- manifest metadata (JSON)
- binary reconstruction recipe
- optional RAW payloads (portable mode)
- integrity metadata

The DNA-style ACGT representation is debug-only and out of scope for container storage.

## Binary Layout
- Header:
  - magic: 4 bytes, ASCII `SBD1`
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
- `format`: `"SBD1"`
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
- SBD-ECO-002 adds remote pin operations for published CIDs via provider adapters.
- Remote pin integration is operational metadata only and does not modify SBD1/SBE1
  bytes, section layout, or integrity/signature semantics.
- `seedbraid publish` may optionally trigger remote pin registration after CID creation.
- `seedbraid pin remote-add` (or equivalent) may register an existing CID with a remote
  pinning provider.

## DVC Workflow Bridge (Operational, No Wire-Format Change)
- SBD-ECO-003 adds DVC integration recipes/scripts under `examples/dvc/` for
  `encode -> verify -> fetch` workflows.
- The bridge reuses existing artifact formats only:
  - seed: `*.sbd` (`SBD1`/`SBE1`)
  - genome snapshot: `*.sgs` (`SGS1`)
  - metadata sidecars: UTF-8 text/JSON files (for example CID and verify marker)
- DVC tracking metadata does not modify seed/genome bytes.
- Integrity enforcement remains `seedbraid verify --strict`; verification failure is
  expected to fail the corresponding pipeline stage.

## OCI/ORAS Artifact Distribution (Operational, No Wire-Format Change)
- SBD-ECO-004 adds ORAS push/pull scripts for distributing `*.sbd` seeds through
  OCI registries.
- Distribution uses OCI transport metadata only; SBD1/SBE1 bytes are unchanged.
- Defined media/metadata conventions:
  - OCI artifact type: `application/vnd.seedbraid.seed.v1`
  - seed layer media type: `application/vnd.seedbraid.seed.layer.v1+sbd`
  - annotations:
    - `io.seedbraid.seed.source-sha256`
    - `io.seedbraid.seed.chunker`
    - `io.seedbraid.seed.manifest-private`
    - `org.opencontainers.image.title`
- Annotation values come from seed manifest fields and are serialized as strings.
- `oras push`/`oras pull` must preserve seed bytes exactly; post-pull integrity is
  enforced by running `seedbraid verify` against the pulled seed.

## ML Tooling Hooks (Operational, No Wire-Format Change)
- SBD-ECO-005 adds optional scripts for logging Seedbraid seed metadata to MLflow and
  uploading seed + metadata sidecars to Hugging Face Hub.
- Added metadata is sidecar JSON only and does not mutate SBD1/SBE1 bytes.
- Sidecar metadata is derived from seed manifest + seed file digest and may include
  optional transport pointers (for example IPFS CID or OCI reference).
- Reproducible restore still depends on `seedbraid verify --strict` using:
  - retrieved seed bytes
  - matching genome path (or portable RAW coverage)
  - optional encryption key for SBE1 seeds
- Security requirement: metadata can expose provenance fields (`source_sha256`,
  chunker profile, transport references); public uploads should use
  `--manifest-private` and encrypted seeds when needed.

## Versioning
- Backward-incompatible changes require `version` increment and docs update.
- New optional sections may be added via TLV without changing version.

## Compatibility Policy
- Seedbraid keeps fixture seeds under `tests/fixtures/compat/v1/` as the canonical
  compatibility corpus for SBD1 v1.
- CI must parse and strictly verify these fixtures on every change.
- Repository CI baseline is defined in `.github/workflows/ci.yml` and includes
  lint (`ruff check .`), full tests (`python -m pytest`), fixture compatibility
  tests (`python -m pytest tests/test_compat_fixtures.py`), and benchmark gates.
- Optional publish workflow (`.github/workflows/publish-seed.yml`) is manual and
  runs `seedbraid encode` + strict `seedbraid verify` before optional IPFS publish
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

## Encrypted Seed Wrapper (SBE1)
For optional at-rest encryption, Seedbraid wraps SBD1 bytes in `SBE1` format.

### SBE1 v1 Layout (16-byte header)

- magic: 4 bytes, ASCII `SBE1`
- version: uint16 (`1`)
- salt_len: uint8 (`16`)
- nonce_len: uint8 (`16`)
- ciphertext_len: uint64
- salt: `salt_len` bytes
- nonce: `nonce_len` bytes
- ciphertext: `ciphertext_len` bytes
- mac: 32 bytes (`HMAC-SHA256`)

KDF parameters for v1 are implicit: scrypt n=16384, r=8, p=1.

### SBE1 v2 Layout (24-byte header)

- magic: 4 bytes, ASCII `SBE1`
- version: uint16 (`2`)
- salt_len: uint8 (`16`)
- nonce_len: uint8 (`16`)
- ciphertext_len: uint64
- scrypt_n: uint32 big-endian (`32768`)
- scrypt_r: uint8 (`8`)
- scrypt_p: uint8 (`1`)
- reserved: uint16 (`0`, must be zero; for future use)
- salt: `salt_len` bytes
- nonce: `nonce_len` bytes
- ciphertext: `ciphertext_len` bytes
- mac: 32 bytes (`HMAC-SHA256`)

### SBE1 v3 Layout (28-byte header, AEAD)

- magic: 4 bytes, ASCII `SBE1`
- version: uint16 (`3`)
- algo_id: uint8 (`0x01` = AES-256-GCM, `0x02` = ChaCha20-Poly1305)
- salt_len: uint8 (`16`)
- nonce_len: uint8 (`12`)
- reserved_a: uint8 (must be `0`)
- reserved_b: uint8 (must be `0`)
- reserved_c: uint8 (must be `0`)
- ciphertext_len: uint64 (includes 16-byte AEAD auth tag)
- scrypt_n: uint32 big-endian (`32768`)
- scrypt_r: uint8 (`8`)
- scrypt_p: uint8 (`1`)
- reserved2: uint16 (`0`, must be zero)
- salt: `salt_len` bytes
- nonce: `nonce_len` bytes
- ciphertext: `ciphertext_len - 16` bytes
- auth_tag: 16 bytes (GCM or Poly1305 authentication tag)

Algorithm IDs:

| ID | Algorithm | Standard |
|----|-----------|----------|
| `0x01` | AES-256-GCM | NIST SP 800-38D |
| `0x02` | ChaCha20-Poly1305 | RFC 8439 |

Key derivation: scrypt produces 32-byte base key, then HKDF-SHA256 Expand
(RFC 5869) with `info=b"seedbraid-sbe1-v3-aead-key"` produces the 32-byte
AEAD key. No separate MAC key is needed.

### Version Negotiation
- New encryptions produce v3 headers when `cryptography` package is available;
  fall back to v2 headers otherwise.
- Decryption accepts v1, v2, and v3: v1 uses implicit scrypt params (n=16384),
  v2 reads params from header, v3 reads params and algorithm from header.
- scrypt_n must be >= 16384 to prevent KDF cost downgrade attacks.
- Reserved fields must be 0; non-zero values are rejected until semantics are defined.

### Semantics
- Plain SBD1 payload is encrypted with a key derived from passphrase + salt.
- **v1/v2**: MAC covers the full payload (header + salt + nonce + ciphertext),
  so header parameters including scrypt_n/r/p are MAC-authenticated.
  MAC is validated before decryption output is accepted.
- **v3**: AEAD (AES-256-GCM) with the 28-byte header as Additional Authenticated
  Data (AAD). The header — including algorithm, KDF parameters, and nonce — is
  bound to the ciphertext by the AEAD auth tag. No external HMAC-SHA256 MAC.
- On authentication failure, parser must fail with explicit tamper/wrong-key error.
- Seedbraid CLI provides `seedbraid gen-encryption-key` to generate a high-entropy
  passphrase for `SB_ENCRYPTION_KEY` usage; this helper does not change
  SBE1 wire format.
- Existing unencrypted SBD1 files remain valid and unchanged.

## Genes Pack (Optional Utility Format)
For `seedbraid export-genes` / `seedbraid import-genes`, Seedbraid defines a small sidecar binary format:
- magic: 5 bytes, ASCII `GENE1`
- count: uint32
- repeated `count` times:
  - hash: 32 bytes (sha256)
  - size: uint32
  - payload: `size` bytes

If `size == 0`, payload is absent (export side could not find this chunk in genome).

## Genome Snapshot Format (SGS1)
For `seedbraid genome snapshot` / `seedbraid genome restore`, Seedbraid defines a binary snapshot format:
- magic: 4 bytes, ASCII `SGS1`
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
