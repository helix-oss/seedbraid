# Helix v2 Threat Model

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

## Encryption Option Policy (Future)
- Add optional envelope encryption section:
  - AEAD-encrypted payload sections
  - key wrapping via recipient public key(s)
- Keep manifest split into public/private parts to reduce metadata leakage.
