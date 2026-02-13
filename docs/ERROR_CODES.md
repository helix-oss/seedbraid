# Helix Error Codes

This document defines operator-facing error codes emitted by the Helix CLI.

## Format
- Prefix: `HELIX_E_`
- Stability: codes are stable across patch/minor releases.
- Output: CLI prints `error[CODE]: <message>` and `next_action: <hint>` when available.

## Core Codes
- `HELIX_E_UNKNOWN`
  - Unexpected non-Helix exception path.
- `HELIX_E_SEED_FORMAT`
  - Seed/container integrity, parse, or decryption format error.
- `HELIX_E_DECODE`
  - Reconstruction/decode failure.
- `HELIX_E_EXTERNAL_TOOL`
  - Generic external tool failure.

## Operational Codes
- `HELIX_E_IPFS_NOT_FOUND`
  - `ipfs` CLI was not found on `PATH`.
- `HELIX_E_IPFS_PUBLISH`
  - `ipfs add` or pin operation failed.
- `HELIX_E_IPFS_FETCH`
  - `ipfs cat`/gateway fetch failed after retries.
- `HELIX_E_IPFS_PIN_STATUS`
  - Pin status query failed unexpectedly.
- `HELIX_E_REMOTE_PIN_CONFIG`
  - Remote pin request is missing required provider config (endpoint/token).
- `HELIX_E_REMOTE_PIN_AUTH`
  - Remote pin provider rejected authentication/authorization.
- `HELIX_E_REMOTE_PIN_REQUEST`
  - Remote pin provider rejected request as invalid (client-side request issue).
- `HELIX_E_REMOTE_PIN_TIMEOUT`
  - Remote pin request timed out after configured retries.
- `HELIX_E_REMOTE_PIN`
  - Remote pin request failed unexpectedly (server/network/protocol error).
- `HELIX_E_SEED_NOT_FOUND`
  - Seed path passed to publish does not exist.
- `HELIX_E_INVALID_OPTION`
  - Invalid runtime option value (for example retries/backoff bounds).
- `HELIX_E_ENCRYPTION_KEY_MISSING`
  - Encryption requested without key material.
- `HELIX_E_SIGNING_KEY_MISSING`
  - Signing requested without signing key env var.
- `HELIX_E_DOCTOR_CHECK`
  - Doctor check encountered an unexpected exception.

## Guidance
- Add new code entries when introducing a new operator-facing error class.
- Do not silently repurpose an existing code for a different failure family.
