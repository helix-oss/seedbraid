# Helix Threat Model

## Assets
- Source file content represented by chunk references and optional RAW payloads.
- Genome database containing reusable chunk bytes.
- Seed metadata (manifest) including file hashes and chunking parameters.

## Adversary Capabilities
- Observes published seed bytes (e.g., on IPFS).
- Performs dictionary attacks on known files/chunks.
- Tampering attempts against seed bytes.

## Key Risks
1. Content inference from hashes
- Chunk hashes can reveal known plaintext via precomputed dictionaries.

2. Metadata leakage
- Manifest exposes source size, hash, and chunking parameters.

3. Portable mode leakage
- RAW payloads can expose full unknown content directly.

4. Tampering
- Modified container sections could induce corruption if unchecked.

## Current Mitigations
- Integrity section validates manifest, recipe, and full payload CRC32.
- Verify/decode enforce expected output SHA-256.
- Portable mode is opt-in and defaults off.
- Optional encrypted wrapper (`HLE1`) protects seed confidentiality at rest/in transit when passphrase is provided.
- Optional private-manifest mode (`--manifest-private`) reduces exposed metadata fields.
- `helix publish` warns when uploading unencrypted seeds.

## KDF Cost Parameters
- HLE1 v2/v3 embed scrypt parameters (n, r, p) in the header; default is n=32768, r=8, p=1.
- Minimum scrypt_n >= 16384 is enforced before key derivation to prevent KDF cost
  downgrade attacks where an attacker modifies the header to weaken brute-force resistance.
- **v1/v2 (HMAC-SHA256 MAC)**: Parameters are MAC-authenticated. HMAC-SHA256 covers the
  full payload including the header, so any header manipulation (including KDF parameters)
  invalidates the MAC. MAC verification requires the correct passphrase, so the n-floor
  check is the first line of defense against pre-MAC header manipulation.
- **v3 (AEAD AAD)**: The 28-byte header is passed as Additional Authenticated Data (AAD)
  to AES-256-GCM. The AEAD authentication tag binds the full 28-byte header —
  including algo_id, scrypt_n/r/p, salt_len, nonce_len, and ciphertext_len —
  to the ciphertext. Any header modification
  causes AEAD decryption to fail, providing tamper detection without a separate MAC.
  This is a stronger binding than the external HMAC approach because authentication
  is integral to the decryption primitive.
- HLE1 v1 seeds use implicit n=16384 and remain decryptable for backward compatibility.

## Limitations
- CRC32 detects accidental corruption and simple tampering, not cryptographic forgery.
- Encryption is passphrase-based and optional; key distribution and rotation are operator-managed.
- IPFS content addressing is public-by-default once CID is shared.
- Manifest-private mode does not hide recipe structure or chunk hashes.

## Recommended Operational Controls
- Prefer non-portable seeds for sensitive data when receiver has trusted genome.
- Encrypt seed before publication when confidentiality is needed.
- Avoid publishing sensitive manifests; use wrapper metadata encryption.
- Pin only from trusted nodes and maintain local audit logs.

## Policy Profiles
1. Internal-only
- Use non-portable seeds with trusted private genome.
- Use `--encrypt` and managed key rotation.
- Restrict CID distribution to authenticated channels.

2. Partner-share
- Use `--encrypt --manifest-private`.
- Distribute decryption keys out-of-band.
- Prefer time-scoped access and audit logs for CID sharing.

3. Public-distribution
- Assume published CIDs are globally retrievable.
- Publish only seeds safe for public exposure (or strongly encrypted).
- Use signatures and reproducible verify workflow for consumer trust.

## AEAD Migration (HLE1 v3)
- HLE1 v3 replaces the custom SHA-256 counter-mode stream cipher with
  AES-256-GCM (NIST SP 800-38D), eliminating the non-standard encryption
  primitive.
- Key derivation uses HKDF-SHA256 (RFC 5869) instead of ad-hoc
  `SHA-256(base_key || label)`, providing formal domain separation.
- AEAD provides authenticated encryption in a single primitive; the external
  HMAC-SHA256 MAC used in v1/v2 is no longer needed for v3.
- The 28-byte header is passed as AAD, binding algorithm ID, scrypt parameters,
  salt length, and nonce length to the ciphertext. This prevents KDF cost
  downgrade attacks and header manipulation without a separate MAC.
- Algorithm agility is supported via the `algo_id` header field: `0x01` for
  AES-256-GCM, `0x02` reserved for ChaCha20-Poly1305.
- Nonces are 12-byte random (`os.urandom(12)`), suitable for both AES-GCM and
  ChaCha20-Poly1305. Collision probability is negligible for < 2^32 encryptions.
- The `cryptography` package (PyCA) is an optional dependency (`crypto` extra).
  When unavailable, encryption falls back to v2 format; v3 decryption requires
  the package and raises a clear error if missing.
- v1/v2 read support is preserved; existing encrypted seeds remain decryptable
  without code changes.

## Encryption Option Policy (Future)
- Add optional envelope encryption section:
  - key wrapping via recipient public key(s)
- Keep manifest split into public/private parts to reduce metadata leakage.
- Consider KDF migration from scrypt to Argon2id (separate ticket).
