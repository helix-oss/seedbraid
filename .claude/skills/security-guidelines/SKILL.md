---
name: security-guidelines
description: >-
  Provides security principles and threat vectors for seedbraid's
  security-sensitive modules (container.py, codec.py, ipfs.py, ipfs_http.py,
  ipfs_chunks.py, cid.py, chunk_manifest.py, pinning.py). Use when modifying,
  reviewing, or auditing cryptographic, IPFS, or binary format code.
user-invocable: false
---

# Seedbraid Security Guidelines

## Security-Sensitive Modules

- `container.py` — Binary format parsing, magic validation, CRC checks
- `codec.py` — Encryption/decryption (SBE1), signature verification
- `ipfs.py`, `ipfs_http.py`, `ipfs_chunks.py` — IPFS communication, CID handling
- `cid.py` — Content identifier validation
- `chunk_manifest.py` — Chunk-to-CID mapping integrity
- `pinning.py` — Remote pinning service integration

## Mandatory Security Rules

1. **Container parsing MUST validate magic bytes, section lengths, and CRC** before processing — prevent malformed input attacks.
2. **Verify logic MUST NOT silently pass** on integrity mismatch — raise with `SB_E_*` error code and actionable hint.
3. **IPFS subprocess calls MUST sanitize arguments** — no shell injection via user-supplied CIDs or paths.
4. **`seedbraid publish` MUST warn** on unencrypted seed publication — reduce accidental public data leakage.
5. **Encryption uses SBE1 wrapper**; MUST NOT mix SBE1/SBD1 semantics without explicit version handling.

## Key Threat Vectors

1. **Content inference from hashes** — chunk hashes can reveal known plaintext via precomputed dictionaries.
2. **Metadata leakage** — manifest exposes source size, hash, and chunking parameters.
3. **Portable mode leakage** — RAW payloads expose full unknown content directly.
4. **Tampering** — modified container sections could induce corruption if unchecked.
5. **Chunk exposure on public IPFS** — chunks are globally retrievable by CID, unencrypted by default.
6. **Chunk unavailability (GC/unpinned)** — unpinned chunks may be garbage-collected.
7. **Chunk manifest integrity** — tampered `.sbd.chunks.json` could map hashes to wrong CIDs.
8. **Kubo API endpoint exposure** — misconfigured nodes expose full RPC API.
9. **SB_KUBO_API override** — compromised endpoint could return tampered data (but SHA-256 verified).

## Mitigations

- Integrity section validates manifest, recipe, and full payload CRC32.
- Verify/decode enforce expected output SHA-256.
- SBE1 encrypts seed confidentiality at rest/in transit.
- Private-manifest mode reduces exposed metadata.
- IPFS chunk fetches are SHA-256-verified post-retrieval.
- Minimum scrypt_n >= 16384 enforced to prevent KDF cost downgrade.

Always read `docs/THREAT_MODEL.md` before modifying these modules.
See `references/threat-vectors.md` for detailed threat analysis.
