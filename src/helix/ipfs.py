"""IPFS transport: publish, fetch, pin-health, and remote pinning.

Wraps the ``ipfs`` CLI for seed distribution and provides HTTP
gateway fallback for fetch operations.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

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


def _require_ipfs() -> str:
    ipfs = shutil.which("ipfs")
    if ipfs is None:
        raise ExternalToolError(
            "ipfs CLI not found. Install IPFS and ensure `ipfs` is on PATH. "
            "Check with: `ipfs --version`.",
            code="HELIX_E_IPFS_NOT_FOUND",
            next_action="Install Kubo and verify with `ipfs --version`.",
        )
    return ipfs


def publish_seed(seed_path: str | Path, pin: bool = False) -> str:
    """Publish a seed file to IPFS and return its CID.

    Adds the seed via ``ipfs add`` and optionally
    pins it locally.

    Args:
        seed_path: Path to the ``.hlx`` seed file.
        pin: Pin the CID locally after publishing.

    Returns:
        Content identifier (CID) string returned by
        IPFS.

    Raises:
        ExternalToolError: If the ``ipfs`` CLI is
            missing, the daemon is unreachable, or
            the pin operation fails.
    """
    ipfs = _require_ipfs()
    seed_path = Path(seed_path)
    if not seed_path.exists():
        raise ExternalToolError(
            f"Seed file not found: {seed_path}",
            code="HELIX_E_SEED_NOT_FOUND",
            next_action=(
                "Provide an existing seed file"
                " path to `helix publish`."
            ),
        )

    proc = subprocess.run(
        [ipfs, "add", "-Q", str(seed_path)],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "ipfs add failed"
        raise ExternalToolError(
            f"Failed to publish seed to IPFS: {msg}",
            code="HELIX_E_IPFS_PUBLISH",
            next_action="Ensure IPFS daemon is running and retry publish.",
        )

    cid = proc.stdout.strip()
    if not cid:
        raise ExternalToolError(
            "IPFS publish did not return CID.",
            code="HELIX_E_IPFS_PUBLISH",
            next_action="Retry `helix publish` and inspect ipfs daemon logs.",
        )

    if pin:
        pin_proc = subprocess.run(
            [ipfs, "pin", "add", cid],
            check=False,
            text=True,
            capture_output=True,
        )
        if pin_proc.returncode != 0:
            msg = (
                pin_proc.stderr.strip()
                or pin_proc.stdout.strip()
                or "ipfs pin add failed"
            )
            raise ExternalToolError(
                f"Published CID {cid},"
                f" but pin failed: {msg}",
                code="HELIX_E_IPFS_PUBLISH",
                next_action=(
                    "Run `ipfs pin add <cid>`"
                    " manually and verify"
                    " node health."
                ),
            )

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
            code="HELIX_E_SEED_FORMAT",
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
            code="HELIX_E_IPFS_FETCH",
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

    Retries ``ipfs cat`` with exponential backoff.
    Falls back to an HTTP gateway when provided.
    Validates the fetched seed before returning.

    Args:
        cid: IPFS content identifier to fetch.
        out_path: Destination file path for the
            downloaded seed.
        retries: Maximum number of ``ipfs cat``
            attempts.
        backoff_ms: Initial backoff in milliseconds,
            doubled on each retry.
        gateway: Optional HTTP gateway URL for
            fallback (e.g.
            ``"https://ipfs.io/ipfs"``).

    Raises:
        ExternalToolError: If all fetch attempts fail
            or the fetched data is not a valid seed.
    """
    ipfs = _require_ipfs()
    out_path = Path(out_path)
    if retries < 1:
        raise ExternalToolError(
            "Fetch retries must be >= 1.",
            code="HELIX_E_INVALID_OPTION",
            next_action="Use `--retries` with value >= 1.",
        )
    if backoff_ms < 0:
        raise ExternalToolError(
            "Fetch backoff must be >= 0ms.",
            code="HELIX_E_INVALID_OPTION",
            next_action="Use `--backoff-ms` with value >= 0.",
        )

    last_err = "ipfs cat failed"
    for attempt in range(1, retries + 1):
        proc = subprocess.run(
            [ipfs, "cat", cid],
            check=False,
            capture_output=True,
        )
        if proc.returncode == 0:
            _validate_fetched_seed_blob(cid, out_path, proc.stdout)
            return
        last_err = (
            proc.stderr.decode("utf-8", errors="replace")
            .strip() or "ipfs cat failed"
        )
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
        code="HELIX_E_IPFS_FETCH",
        next_action=(
            "Use `helix fetch <cid> --gateway https://ipfs.io/ipfs` "
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
    ipfs = _require_ipfs()

    pin_proc = subprocess.run(
        [ipfs, "pin", "ls", cid],
        check=False,
        text=True,
        capture_output=True,
    )
    if pin_proc.returncode == 0:
        pinned = True
        pin_type = None
        pin_line = pin_proc.stdout.strip().splitlines()
        if pin_line:
            parts = pin_line[0].split()
            if len(parts) >= 2:
                pin_type = parts[-1]
        pin_reason = None
    else:
        pin_msg = (
            pin_proc.stderr.strip()
            or pin_proc.stdout.strip()
            or "pin status check failed"
        )
        lowered = pin_msg.lower()
        if "not pinned" in lowered or "is not pinned" in lowered:
            pinned = False
            pin_type = None
            pin_reason = pin_msg
        else:
            raise ExternalToolError(
                "Failed to query pin status"
                f" for CID {cid}: {pin_msg}",
                code="HELIX_E_IPFS_PIN_STATUS",
                next_action=(
                    "Verify IPFS daemon is running"
                    " and retry"
                    " `helix pin-health <cid>`."
                ),
            )

    block_proc = subprocess.run(
        [ipfs, "block", "stat", cid],
        check=False,
        text=True,
        capture_output=True,
    )
    block_available = block_proc.returncode == 0
    block_reason = None
    if not block_available:
        block_reason = (
            block_proc.stderr.strip()
            or block_proc.stdout.strip()
            or "block availability check failed"
        )

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
    environment variables (``HELIX_PINNING_ENDPOINT``,
    ``HELIX_PINNING_TOKEN``).

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
    resolved_endpoint = endpoint or os.environ.get("HELIX_PINNING_ENDPOINT")
    resolved_token = token or os.environ.get("HELIX_PINNING_TOKEN")

    missing: list[str] = []
    if not resolved_endpoint:
        missing.append("endpoint")
    if not resolved_token:
        missing.append("token")
    if missing:
        missing_csv = ", ".join(missing)
        raise ExternalToolError(
            f"Remote pin configuration is incomplete (missing {missing_csv}).",
            code="HELIX_E_REMOTE_PIN_CONFIG",
            next_action=(
                "Set HELIX_PINNING_ENDPOINT and HELIX_PINNING_TOKEN, "
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
