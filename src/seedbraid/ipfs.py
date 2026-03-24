"""IPFS transport: publish, fetch, pin-health, and remote pinning.

Routes through the ``ipfs_http`` module (kubo HTTP RPC API)
for seed distribution. Provides HTTP gateway fallback for
fetch operations.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import ipfs_http
from .container import (
    is_encrypted_seed_data,
    read_seed,
    validate_encrypted_seed_envelope,
)
from .errors import ExternalToolError, SeedFormatError
from .pinning import (
    RemotePinResult,
    build_remote_pin_provider,
)


def publish_seed(seed_path: str | Path, pin: bool = False) -> str:
    """Publish a seed file to IPFS and return its CID.

    Adds the seed via kubo ``/add`` API and optionally
    pins it locally.

    Args:
        seed_path: Path to the ``.sbd`` seed file.
        pin: Pin the CID locally after publishing.

    Returns:
        Content identifier (CID) string returned by
        IPFS.

    Raises:
        ExternalToolError: If the kubo API is
            unreachable, or the pin operation fails.
    """
    seed_path = Path(seed_path)
    if not seed_path.exists():
        raise ExternalToolError(
            f"Seed file not found: {seed_path}",
            code="SB_E_SEED_NOT_FOUND",
            next_action=(
                "Provide an existing seed file"
                " path to `seedbraid publish`."
            ),
        )

    result = ipfs_http.post_multipart_file_json(
        "/add", seed_path, quieter="true",
    )
    cid: str = result.get("Hash", "")
    if not cid:
        raise ExternalToolError(
            "IPFS publish did not return CID.",
            code="SB_E_IPFS_PUBLISH",
            next_action=(
                "Retry `seedbraid publish` and"
                " inspect ipfs daemon logs."
            ),
        )

    if pin:
        try:
            ipfs_http.post_json("/pin/add", arg=cid)
        except ExternalToolError as exc:
            raise ExternalToolError(
                f"Published CID {cid},"
                f" but pin failed: {exc}",
                code="SB_E_IPFS_PUBLISH",
                next_action=(
                    "Run `ipfs pin add <cid>`"
                    " manually and verify"
                    " node health."
                ),
            ) from exc

    return cid


def _validate_fetched_seed_blob(cid: str, out_path: Path, blob: bytes) -> None:
    out_path.write_bytes(blob)

    try:
        if is_encrypted_seed_data(blob):
            # Encrypted seeds cannot be fully parsed
            # without a key at fetch time.  Validate
            # envelope structure and defer full
            # validation to decode/verify.
            validate_encrypted_seed_envelope(blob)
            return
        read_seed(out_path)
    except SeedFormatError as exc:
        raise ExternalToolError(
            f"Fetched bytes for CID {cid}, but"
            " integrity/manifest validation"
            f" failed: {exc}",
            code="SB_E_SEED_FORMAT",
            next_action=(
                "Refetch the CID or verify publisher"
                " integrity before decode."
            ),
        ) from exc


def _fetch_from_gateway(cid: str, gateway: str) -> bytes:
    url = f"{gateway.rstrip('/')}/{cid}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()  # type: ignore[no-any-return]
    except (urllib.error.URLError, OSError) as exc:
        raise ExternalToolError(
            f"Gateway fetch failed ({url}): {exc}",
            code="SB_E_IPFS_FETCH",
            next_action=(
                "Try another gateway or confirm"
                " network access from this"
                " environment."
            ),
        ) from exc


def fetch_seed(
    cid: str,
    out_path: str | Path,
    *,
    retries: int = 3,
    backoff_ms: int = 200,
    gateway: str | None = None,
) -> None:
    """Fetch a seed from IPFS by CID and write it to disk.

    Retries kubo ``/cat`` API with exponential backoff.
    Falls back to an HTTP gateway when provided.
    Validates the fetched seed before returning.

    Args:
        cid: IPFS content identifier to fetch.
        out_path: Destination file path for the
            downloaded seed.
        retries: Maximum number of fetch attempts.
        backoff_ms: Initial backoff in milliseconds,
            doubled on each retry.
        gateway: Optional HTTP gateway URL for
            fallback (e.g.
            ``"https://ipfs.io/ipfs"``).

    Raises:
        ExternalToolError: If all fetch attempts fail
            or the fetched data is not a valid seed.
    """
    out_path = Path(out_path)
    if retries < 1:
        raise ExternalToolError(
            "Fetch retries must be >= 1.",
            code="SB_E_INVALID_OPTION",
            next_action="Use `--retries` with value >= 1.",
        )
    if backoff_ms < 0:
        raise ExternalToolError(
            "Fetch backoff must be >= 0ms.",
            code="SB_E_INVALID_OPTION",
            next_action="Use `--backoff-ms` with value >= 0.",
        )

    last_err = "ipfs cat failed"
    for attempt in range(1, retries + 1):
        try:
            blob = ipfs_http.post_raw("/cat", arg=cid)
            _validate_fetched_seed_blob(cid, out_path, blob)
            return
        except ExternalToolError as exc:
            last_err = str(exc)
        if attempt < retries and backoff_ms > 0:
            time.sleep((backoff_ms * (2 ** (attempt - 1))) / 1000)

    gateway_err: str | None = None
    if gateway:
        try:
            blob = _fetch_from_gateway(cid, gateway)
            _validate_fetched_seed_blob(cid, out_path, blob)
            return
        except ExternalToolError as exc:
            gateway_err = str(exc)

    detail = (
        f"Failed to fetch CID {cid} after {retries} attempt(s) via ipfs cat. "
        f"Last error: {last_err}."
    )
    if gateway and gateway_err:
        detail += f" Gateway fallback also failed: {gateway_err}."
    detail += (
        " Next action: verify local IPFS daemon"
        " connectivity, confirm CID availability,"
        " or provide --gateway"
        " https://<gateway>/ipfs."
    )
    raise ExternalToolError(
        detail,
        code="SB_E_IPFS_FETCH",
        next_action=(
            "Use `seedbraid fetch <cid> --gateway https://ipfs.io/ipfs` "
            "or check IPFS node health."
        ),
    )


def pin_health_status(cid: str) -> dict[str, str | bool | None]:
    """Check local pin status and block availability.

    Queries the IPFS node for pin state and block
    reachability of the given CID.

    Args:
        cid: IPFS content identifier to check.

    Returns:
        Dict with keys ``"cid"``, ``"pinned"``
        (bool), ``"pin_type"`` (str or None),
        ``"block_available"`` (bool), ``"ok"``
        (bool), and ``"reason"`` (str or None).

    Raises:
        ExternalToolError: If the IPFS daemon is
            unreachable or the pin query fails
            unexpectedly.
    """
    try:
        pin_result = ipfs_http.post_json(
            "/pin/ls", arg=cid,
        )
        pinned = True
        keys = pin_result.get("Keys", {})
        pin_type = None
        if cid in keys:
            pin_type = keys[cid].get("Type")
        pin_reason = None
    except ExternalToolError as exc:
        msg = str(exc).lower()
        if "not pinned" in msg or "is not pinned" in msg:
            pinned = False
            pin_type = None
            pin_reason = str(exc)
        else:
            raise

    try:
        ipfs_http.post_json("/block/stat", arg=cid)
        block_available = True
        block_reason = None
    except ExternalToolError as exc:
        block_available = False
        block_reason = str(exc)

    reason = pin_reason or block_reason
    if pin_reason and block_reason:
        reason = f"{pin_reason}; {block_reason}"

    return {
        "cid": cid,
        "pinned": pinned,
        "pin_type": pin_type,
        "block_available": block_available,
        "ok": pinned and block_available,
        "reason": reason,
    }


def remote_pin_cid(
    cid: str,
    *,
    provider: str = "psa",
    endpoint: str | None = None,
    token: str | None = None,
    name: str | None = None,
    timeout_ms: int = 10_000,
    retries: int = 3,
    backoff_ms: int = 200,
) -> RemotePinResult:
    """Register a CID with a remote pinning provider.

    Resolves endpoint and token from arguments or
    environment variables (``SB_PINNING_ENDPOINT``,
    ``SB_PINNING_TOKEN``).

    Args:
        cid: IPFS content identifier to pin.
        provider: Provider type.  Currently only
            ``"psa"`` (Pinning Services API) is
            supported.
        endpoint: Provider API endpoint URL.
        token: Bearer token for authentication.
        name: Optional human-readable pin name.
        timeout_ms: Request timeout in milliseconds.
        retries: Maximum number of attempts.
        backoff_ms: Initial backoff in milliseconds.

    Returns:
        Result with provider, CID, status, and
        optional request ID.

    Raises:
        ExternalToolError: If configuration is
            incomplete or all attempts fail.
    """
    resolved_endpoint = endpoint or os.environ.get("SB_PINNING_ENDPOINT")
    resolved_token = token or os.environ.get("SB_PINNING_TOKEN")

    missing: list[str] = []
    if not resolved_endpoint:
        missing.append("endpoint")
    if not resolved_token:
        missing.append("token")
    if missing:
        missing_csv = ", ".join(missing)
        raise ExternalToolError(
            f"Remote pin configuration is incomplete (missing {missing_csv}).",
            code="SB_E_REMOTE_PIN_CONFIG",
            next_action=(
                "Set SB_PINNING_ENDPOINT and SB_PINNING_TOKEN, "
                "or pass --endpoint/--token explicitly."
            ),
        )

    adapter = build_remote_pin_provider(
        provider,
        endpoint=str(resolved_endpoint),
        token=str(resolved_token),
    )
    return adapter.remote_add(
        cid,
        name=name,
        timeout_ms=timeout_ms,
        retries=retries,
        backoff_ms=backoff_ms,
    )
