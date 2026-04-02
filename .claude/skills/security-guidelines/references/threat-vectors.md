# Seedbraid Threat Vectors (Reference)

Source: `docs/THREAT_MODEL.md`

## Assets
- Source file content represented by chunk references and optional RAW payloads.
- Genome database containing reusable chunk bytes.
- Seed metadata (manifest) including file hashes and chunking parameters.

## Adversary Capabilities
- Observes published seed bytes (e.g., on IPFS).
- Performs dictionary attacks on known files/chunks.
- Tampering attempts against seed bytes.

## Threat Details

### 1. Content Inference from Hashes
Chunk hashes can reveal known plaintext via precomputed dictionaries.
Mitigation: SBE1 encryption, private-manifest mode.

### 2. Metadata Leakage
Manifest exposes source size, hash, and chunking parameters.
Mitigation: `--manifest-private` flag.

### 3. Portable Mode Leakage
RAW payloads can expose full unknown content directly.
Mitigation: Portable mode is opt-in and defaults off.

### 4. Tampering
Modified container sections could induce corruption if unchecked.
Mitigation: Integrity section CRC32, verify/decode SHA-256 enforcement.

### 5. Chunk Exposure on Public IPFS
Individual chunks published to IPFS are globally retrievable by CID.
Mitigation: Encryption warning on publish, SBE1 wrapper.

### 6. Chunk Unavailability (GC/Unpinned)
Unpinned chunks may be garbage-collected by IPFS nodes.
Mitigation: DAG pinning via MFS root CID.

### 7. Chunk Manifest Integrity
Tampered `.sbd.chunks.json` sidecar could map hashes to wrong CIDs.
Mitigation: Fetched chunks are SHA-256-verified against recipe hash table.

### 8. Kubo API Endpoint Exposure
Default kubo API listens on localhost only. Misconfigured nodes expose full RPC.
Mitigation: seedbraid does not modify kubo listener config.

### 9. SB_KUBO_API Override
Compromised endpoint could return tampered data.
Mitigation: SHA-256 verification post-fetch regardless of endpoint.

## KDF Security
- SBE1 v3 uses AES-256-GCM with scrypt KDF.
- Minimum scrypt_n >= 16384 enforced to prevent cost downgrade attacks.
- v3 AEAD binds the 28-byte header as AAD — any header manipulation fails decryption.
