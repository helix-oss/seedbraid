---
name: sbd1-format
description: >-
  Provides knowledge about the SBD1 binary seed format, TLV section structure,
  magic bytes, and container logic. Use when working on container.py, codec.py,
  or any code that reads or writes .sbd files. References docs/FORMAT.md for the
  complete specification.
user-invocable: false
---

# SBD1 Binary Format Guide

## Container Structure

- **Magic**: 4 bytes ASCII `SBD1`
- **Version**: uint16 big-endian (current: `1`)
- **Section count**: uint16 big-endian
- **Sections**: TLV (Type-Length-Value) entries
  - Type: uint16 big-endian
  - Length: uint64 big-endian
  - Value: `length` bytes

## Section Types

| Type | Name | Required | Description |
|------|------|----------|-------------|
| 1 | Manifest | Yes | JSON metadata (compressed) |
| 2 | Recipe | Yes | Binary reconstruction operations |
| 3 | RAW payload | No | Inline chunk data (portable mode) |
| 4 | Integrity | Yes | CRC32 validation |
| 5 | Signature | No | Ed25519 signature |

Unknown section types are ignored if integrity is still verifiable.

## Key Formats

- **SBD1** (`.sbd`): Seed container
- **SBE1** (`.sbe`): Encrypted wrapper (AES-256-GCM with scrypt KDF)
- **SGS1** (`.sgs`): Genome snapshot

## Manifest JSON Fields

- `format`: `"SBD1"`, `version`: `1`
- `source_size`, `source_sha256`: original file info
- `chunker`: CDC parameters `{name, min, avg, max, window_size}`
- `portable`, `learn`: mode flags
- `stats`: chunk statistics
- `created_at`: RFC3339 UTC

## Recipe Operations

- `REF(hash_index)`: retrieve chunk by SHA-256 hash from genome
- `RAW(hash_index)`: retrieve chunk from RAW table

## Important Rules

- Always validate magic bytes before processing.
- Section lengths must be bounds-checked to prevent buffer overflows.
- CRC32 in Integrity section covers manifest + recipe + RAW sections.
- Backward compatibility: never change existing section semantics without version bump.

See `references/format-essentials.md` for detailed binary layout.
Read `docs/FORMAT.md` for the complete specification.
