from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import ExternalToolError, HelixError
from .storage import resolve_genome_db_path


@dataclass(frozen=True)
class DoctorCheck:
    check: str
    status: str
    detail: str
    next_action: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "ok")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def ok(self) -> bool:
        return self.fail_count == 0


def _check_python_version() -> DoctorCheck:
    major = sys.version_info.major
    minor = sys.version_info.minor
    detail = f"python={major}.{minor}"
    if (major, minor) >= (3, 12):
        return DoctorCheck(check="python", status="ok", detail=detail)
    return DoctorCheck(
        check="python",
        status="fail",
        detail=f"{detail} (requires >=3.12)",
        next_action=(
            "Install Python 3.12+ and recreate"
            " the project virtual environment."
        ),
    )


def _check_ipfs_cli() -> DoctorCheck:
    ipfs = shutil.which("ipfs")
    if ipfs is None:
        return DoctorCheck(
            check="ipfs_cli",
            status="fail",
            detail="ipfs binary not found on PATH",
            next_action="Install Kubo and verify with `ipfs --version`.",
        )
    proc = subprocess.run(
        [ipfs, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (
            proc.stderr.strip()
            or proc.stdout.strip()
            or "version check failed"
        )
        return DoctorCheck(
            check="ipfs_cli",
            status="fail",
            detail=f"ipfs command failed: {msg}",
            next_action=(
                "Ensure ipfs is executable and"
                " PATH points to the correct"
                " binary."
            ),
        )
    version = proc.stdout.strip() or proc.stderr.strip() or "unknown"
    return DoctorCheck(check="ipfs_cli", status="ok", detail=version)


def _check_ipfs_path() -> DoctorCheck:
    ipfs_path = os.environ.get("IPFS_PATH")
    if not ipfs_path:
        return DoctorCheck(
            check="ipfs_repo",
            status="warn",
            detail="IPFS_PATH is unset (using default ~/.ipfs)",
            next_action="Set IPFS_PATH for isolated environments when needed.",
        )
    p = Path(ipfs_path)
    if not p.exists():
        return DoctorCheck(
            check="ipfs_repo",
            status="warn",
            detail=f"IPFS_PATH does not exist: {p}",
            next_action=(
                "Run `ipfs init` for this"
                " IPFS_PATH before"
                " publish/fetch operations."
            ),
        )
    if not p.is_dir():
        return DoctorCheck(
            check="ipfs_repo",
            status="fail",
            detail=f"IPFS_PATH is not a directory: {p}",
            next_action="Set IPFS_PATH to a valid writable directory.",
        )
    return DoctorCheck(check="ipfs_repo", status="ok", detail=f"IPFS_PATH={p}")


def _check_genome_path(genome_path: Path) -> DoctorCheck:
    db_path = resolve_genome_db_path(genome_path)
    parent = db_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"cannot create parent directory {parent}: {exc}",
            next_action="Choose a writable --genome path.",
        )

    if not os.access(parent, os.W_OK):
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"directory is not writable: {parent}",
            next_action=(
                "Adjust directory permissions"
                " or select another"
                " --genome path."
            ),
        )

    try:
        with tempfile.NamedTemporaryFile(
            dir=parent,
            prefix=".helix-doctor-",
            delete=True,
        ):
            pass
    except OSError as exc:
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"write test failed under {parent}: {exc}",
            next_action="Fix filesystem permissions for genome storage.",
        )

    return DoctorCheck(
        check="genome_path",
        status="ok",
        detail=f"db_path={db_path}",
    )


def _check_compression() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = [
        DoctorCheck(
            check="compression_zlib",
            status="ok",
            detail="zlib available (stdlib)",
        )
    ]
    if importlib.util.find_spec("zstandard") is None:
        checks.append(
            DoctorCheck(
                check="compression_zstd",
                status="warn",
                detail="optional dependency 'zstandard' is not installed",
                next_action=(
                    "Run `uv sync --extra zstd`"
                    " to enable --compression zstd."
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                check="compression_zstd",
                status="ok",
                detail="zstandard available",
            )
        )
    return checks


def run_doctor(genome_path: str | Path) -> DoctorReport:
    path = Path(genome_path)
    checks: list[DoctorCheck] = []
    try:
        checks.append(_check_python_version())
        checks.append(_check_ipfs_cli())
        checks.append(_check_ipfs_path())
        checks.append(_check_genome_path(path))
        checks.extend(_check_compression())
    except HelixError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExternalToolError(
            f"doctor failed unexpectedly: {exc}",
            code="HELIX_E_DOCTOR_CHECK",
            next_action=(
                "Re-run `helix doctor --genome <path>`"
                " and inspect environment setup."
            ),
        ) from exc
    return DoctorReport(checks=checks)
