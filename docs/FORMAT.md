# HLX1 Seed Container Format

## Overview
HLX1 is a binary seed container used by Helix v2. It stores:
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

## Decode/Verify Requirements
- Parser must validate magic/version and integrity section.
- For lossless mode, decode output SHA-256 must equal `manifest.source_sha256`.
- Verify must report missing required chunk hashes when genome/raw are insufficient.

## Versioning
- Backward-incompatible changes require `version` increment and docs update.
- New optional sections may be added via TLV without changing version.

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
