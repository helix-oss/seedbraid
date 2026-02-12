from __future__ import annotations

import shutil
import subprocess
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


def fetch_seed(cid: str, out_path: str | Path) -> None:
    ipfs = _require_ipfs()
    out_path = Path(out_path)

    proc = subprocess.run(
        [ipfs, "cat", cid],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", errors="replace").strip() or "ipfs cat failed"
        raise ExternalToolError(f"Failed to fetch CID {cid}: {msg}")

    blob = proc.stdout
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
