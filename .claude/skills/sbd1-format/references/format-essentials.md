# SBD1 Format Essentials (Reference)

Source: `docs/FORMAT.md`

## Binary Layout Detail

### Header (8 bytes)
```
Offset  Size    Field
0       4       Magic: ASCII "SBD1"
4       2       Version: uint16 BE (1)
6       2       Section count: uint16 BE
```

### Section Entry
```
Offset  Size    Field
0       2       Type: uint16 BE
2       8       Length: uint64 BE
10      N       Value: `length` bytes
```

### Manifest Section (Type 1)
- compression_id: uint8 (0=none, 1=zlib, 2=zstd)
- compressed_manifest_bytes: remaining bytes

### Recipe Section (Type 2)
- op_count: uint32
- hash_count: uint32
- hash_table: hash_count * 32 bytes (SHA-256 digests)
- ops: op_count entries of {opcode: uint8, hash_index: uint32}
  - opcode 1 = REF, opcode 2 = RAW

### RAW Section (Type 3)
- count: uint32
- entries: {hash_index: uint32, length: uint32, data: `length` bytes}

### Integrity Section (Type 4)
- crc32: uint32 (covers sections 1-3)

### Signature Section (Type 5)
- algo_id: uint8 (1 = Ed25519)
- public_key: 32 bytes
- signature: 64 bytes
- Covers sections 1-4

## SBE1 Encrypted Wrapper
- Magic: ASCII "SBE1"
- Version: uint8 (1=HMAC-SHA256, 2=scrypt params, 3=AEAD)
- v3 uses AES-256-GCM with scrypt KDF
- HKDF info: `seedbraid-sbe1-v3-aead-key`
- Minimum scrypt_n >= 16384 enforced

## SGS1 Genome Snapshot
- Magic: ASCII "SGS1"
- Contains exported genome chunks for portability
