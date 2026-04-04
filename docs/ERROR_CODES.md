# Seedbraid Error Codes

This document defines operator-facing error codes emitted by the Seedbraid CLI.

## Format
- Prefix: `SB_E_`
- Stability: codes are stable across patch/minor releases.
- Output: CLI prints `error[CODE]: <message>` and `next_action: <hint>` when available.

## Core Codes
- `SB_E_UNKNOWN`
  - Unexpected non-Seedbraid exception path.
- `SB_E_SEED_FORMAT`
  - Seed/container integrity, parse, or decryption format error.
- `SB_E_DECODE`
  - Reconstruction/decode failure.
- `SB_E_EXTERNAL_TOOL`
  - Generic external tool failure.

## Operational Codes
- `SB_E_IPFS_NOT_FOUND`
  - kubo HTTP API is unreachable (daemon not running or wrong endpoint).
- `SB_E_IPFS_PUBLISH`
  - `ipfs add` or pin operation failed.
- `SB_E_IPFS_FETCH`
  - `ipfs cat`/gateway fetch failed after retries.
- `SB_E_IPFS_PIN_STATUS`
  - Pin status query failed unexpectedly.
- `SB_E_IPFS_CHUNK_PUT`
  - kubo HTTP `/api/v0/block/put` chunk publish operation failed.
- `SB_E_IPFS_CHUNK_GET`
  - kubo HTTP `/api/v0/block/get` chunk fetch operation failed after retries.
- `SB_E_IPFS_CID_MISMATCH`
  - CID or SHA-256 hash mismatch after IPFS block put or get operation.
    The returned data does not match the expected content hash.
- `SB_E_IPFS_MFS`
  - IPFS MFS operation failed during DAG construction for chunk pinning
    (`/api/v0/files/mkdir`, `/cp`, `/stat`, `/rm`).
- `SB_E_KUBO_API_UNREACHABLE`
  - kubo HTTP API did not respond. Ensure `ipfs daemon` is running
    and the endpoint configured in `SB_KUBO_API` (default
    `http://127.0.0.1:5001/api/v0`) is reachable.
- `SB_E_CHUNK_MANIFEST_FORMAT`
  - Chunk manifest sidecar (`.sbd.chunks.json`) has invalid format,
    unknown version, or missing required fields.
- `SB_E_REMOTE_PIN_CONFIG`
  - Remote pin request is missing required provider config (endpoint/token).
- `SB_E_REMOTE_PIN_AUTH`
  - Remote pin provider rejected authentication/authorization.
- `SB_E_REMOTE_PIN_REQUEST`
  - Remote pin provider rejected request as invalid (client-side request issue).
- `SB_E_REMOTE_PIN_TIMEOUT`
  - Remote pin request timed out after configured retries.
- `SB_E_REMOTE_PIN`
  - Remote pin request failed unexpectedly (server/network/protocol error).
- `SB_E_SEED_NOT_FOUND`
  - Seed path passed to publish does not exist.
- `SB_E_INVALID_OPTION`
  - Invalid runtime option value (for example retries/backoff bounds).
- `SB_E_ENCRYPTION_KEY_MISSING`
  - Encryption requested without key material.
- `SB_E_SIGNING_KEY_MISSING`
  - Signing requested without signing key env var.
- `SB_E_DOCTOR_CHECK`
  - Doctor check encountered an unexpected exception.
- `SB_E_MLFLOW_CONFIG`
  - MLflow metadata logging is missing required configuration.
- `SB_E_MLFLOW_REQUEST`
  - MLflow API request for metadata logging failed.
- `SB_E_HF_CONFIG`
  - Hugging Face upload config is invalid or missing credentials.
- `SB_E_HF_REQUEST`
  - Hugging Face upload request/CLI invocation failed.

## Guidance
- Add new code entries when introducing a new operator-facing error class.
- Do not silently repurpose an existing code for a different failure family.
