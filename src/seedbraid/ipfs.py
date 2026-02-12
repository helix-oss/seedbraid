from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .container import is_encrypted_seed_data, read_seed, validate_encrypted_seed_envelope
from .errors import ExternalToolError, SeedFormatError


def _require_ipfs() -> str:
    ipfs = shutil.which("ipfs")
    if ipfs is None:
        raise ExternalToolError(
            "ipfs CLI not found. Install IPFS and ensure `ipfs` is on PATH. "
            "Check with: `ipfs --version`."
        )
    return ipfs


def publish_seed(seed_path: str | Path, pin: bool = False) -> str:
    ipfs = _require_ipfs()
    seed_path = Path(seed_path)
    if not seed_path.exists():
        raise ExternalToolError(f"Seed file not found: {seed_path}")

    proc = subprocess.run(
        [ipfs, "add", "-Q", str(seed_path)],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "ipfs add failed"
        raise ExternalToolError(f"Failed to publish seed to IPFS: {msg}")

    cid = proc.stdout.strip()
    if not cid:
        raise ExternalToolError("IPFS publish did not return CID.")

    if pin:
        pin_proc = subprocess.run(
            [ipfs, "pin", "add", cid],
            check=False,
            text=True,
            capture_output=True,
        )
        if pin_proc.returncode != 0:
            msg = pin_proc.stderr.strip() or pin_proc.stdout.strip() or "ipfs pin add failed"
            raise ExternalToolError(f"Published CID {cid}, but pin failed: {msg}")

    return cid


def _validate_fetched_seed_blob(cid: str, out_path: Path, blob: bytes) -> None:
    out_path.write_bytes(blob)

    try:
        if is_encrypted_seed_data(blob):
            # Encrypted seeds cannot be fully parsed without a key at fetch time.
            # Validate envelope structure and defer full validation to decode/verify.
            validate_encrypted_seed_envelope(blob)
            return
        read_seed(out_path)
    except SeedFormatError as exc:
        raise ExternalToolError(
            f"Fetched bytes for CID {cid}, but integrity/manifest validation failed: {exc}"
        ) from exc


def _fetch_from_gateway(cid: str, gateway: str) -> bytes:
    url = f"{gateway.rstrip('/')}/{cid}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise ExternalToolError(f"Gateway fetch failed ({url}): {exc}") from exc


def fetch_seed(
    cid: str,
    out_path: str | Path,
    *,
    retries: int = 3,
    backoff_ms: int = 200,
    gateway: str | None = None,
) -> None:
    ipfs = _require_ipfs()
    out_path = Path(out_path)
    if retries < 1:
        raise ExternalToolError("Fetch retries must be >= 1.")
    if backoff_ms < 0:
        raise ExternalToolError("Fetch backoff must be >= 0ms.")

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
        last_err = proc.stderr.decode("utf-8", errors="replace").strip() or "ipfs cat failed"
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
        " Next action: verify local IPFS daemon connectivity, confirm CID availability, "
        "or provide --gateway https://<gateway>/ipfs."
    )
    raise ExternalToolError(detail)


def pin_health_status(cid: str) -> dict[str, str | bool | None]:
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
        pin_msg = pin_proc.stderr.strip() or pin_proc.stdout.strip() or "pin status check failed"
        lowered = pin_msg.lower()
        if "not pinned" in lowered or "is not pinned" in lowered:
            pinned = False
            pin_type = None
            pin_reason = pin_msg
        else:
            raise ExternalToolError(f"Failed to query pin status for CID {cid}: {pin_msg}")

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
