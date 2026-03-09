"""OCI registry integration for Seedbraid seed push/pull via ORAS CLI."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .container import read_seed
from .errors import ExternalToolError

SB_OCI_ARTIFACT_TYPE = "application/vnd.seedbraid.seed.v1"
SB_OCI_SEED_MEDIA_TYPE = "application/vnd.seedbraid.seed.layer.v1+sbd"

ANNOTATION_SOURCE_SHA256 = "io.seedbraid.seed.source-sha256"
ANNOTATION_CHUNKER = "io.seedbraid.seed.chunker"
ANNOTATION_MANIFEST_PRIVATE = "io.seedbraid.seed.manifest-private"
ANNOTATION_TITLE = "org.opencontainers.image.title"


def _require_oras_cli() -> str:
    oras = shutil.which("oras")
    if oras is None:
        raise ExternalToolError(
            "oras CLI not found. Install ORAS and ensure `oras` is on PATH. "
            "Check with: `oras version`.",
            next_action="Install ORAS and verify with `oras version`.",
        )
    return oras


def build_oras_annotations(
    seed_path: str | Path,
    *,
    encryption_key: str | None = None,
) -> dict[str, str]:
    """Build OCI annotation dict from a seed file.

    Extracts source SHA-256, chunker name, manifest
    privacy flag, and title from the seed manifest.

    Args:
        seed_path: Path to the ``.sbd`` seed file.
        encryption_key: Passphrase to decrypt the
            seed if encrypted.  ``None`` for
            unencrypted seeds.

    Returns:
        Dict mapping OCI annotation keys to string
        values.
    """
    seed = read_seed(seed_path, encryption_key=encryption_key)
    manifest = seed.manifest

    source_sha = manifest.get("source_sha256")
    source_sha_value = "null" if source_sha is None else str(source_sha)

    chunker_name = "unknown"
    chunker = manifest.get("chunker")
    if isinstance(chunker, dict) and chunker.get("name"):
        chunker_name = str(chunker["name"])

    return {
        ANNOTATION_SOURCE_SHA256: source_sha_value,
        ANNOTATION_CHUNKER: chunker_name,
        ANNOTATION_MANIFEST_PRIVATE: "true"
        if bool(manifest.get("manifest_private", False))
        else "false",
        ANNOTATION_TITLE: Path(seed_path).name,
    }


def push_seed_oras(
    seed_path: str | Path,
    reference: str,
    *,
    artifact_type: str = SB_OCI_ARTIFACT_TYPE,
    media_type: str = SB_OCI_SEED_MEDIA_TYPE,
    encryption_key: str | None = None,
) -> dict[str, str]:
    """Push a seed to an OCI registry via ORAS CLI.

    Attaches OCI annotations derived from the seed
    manifest.

    Args:
        seed_path: Path to the ``.sbd`` seed file.
        reference: OCI reference in the format
            ``<registry>/<repo>:<tag>``.
        artifact_type: OCI artifact type string.
        media_type: Media type for the seed layer.
        encryption_key: Passphrase to decrypt the
            seed for annotation extraction.

    Returns:
        Dict of OCI annotations attached to the
        pushed artifact.

    Raises:
        ExternalToolError: If the ``oras`` CLI is
            missing, the seed file does not exist,
            or the push fails.
    """
    seed_path = Path(seed_path)
    if not seed_path.exists():
        raise ExternalToolError(
            f"Seed file not found: {seed_path}",
            code="SB_E_SEED_NOT_FOUND",
            next_action="Provide an existing seed path ending in `.sbd`.",
        )

    oras = _require_oras_cli()
    annotations = build_oras_annotations(
        seed_path, encryption_key=encryption_key,
    )

    cmd = [
        oras,
        "push",
        reference,
        f"{seed_path.name}:{media_type}",
        "--artifact-type",
        artifact_type,
    ]
    for key, value in sorted(annotations.items()):
        cmd.extend(["--annotation", f"{key}={value}"])

    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
        cwd=seed_path.parent,
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "oras push failed"
        raise ExternalToolError(
            f"Failed to push seed to OCI registry: {msg}",
            next_action=(
                "Run `oras login <registry>` first, verify write permissions, "
                "and confirm reference format `<registry>/<repo>:<tag>`."
            ),
        )

    return annotations


def pull_seed_oras(reference: str, out_path: str | Path) -> Path:
    """Pull a seed from an OCI registry via ORAS CLI.

    Downloads the artifact into a temporary directory,
    verifies that exactly one ``.sbd`` file is
    present, and copies it to ``out_path``.

    Args:
        reference: OCI reference in the format
            ``<registry>/<repo>:<tag>``.
        out_path: Destination file path for the
            pulled seed.

    Returns:
        The ``out_path`` as a ``Path`` object.

    Raises:
        ExternalToolError: If the ``oras`` CLI is
            missing, the pull fails, or the artifact
            does not contain exactly one ``.sbd``
            file.
    """
    out_path = Path(out_path)
    oras = _require_oras_cli()

    with tempfile.TemporaryDirectory(prefix="seedbraid-oras-pull-") as tmp:
        cmd = [oras, "pull", reference, "-o", tmp]
        proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
        if proc.returncode != 0:
            msg = (
                proc.stderr.strip()
                or proc.stdout.strip()
                or "oras pull failed"
            )
            raise ExternalToolError(
                f"Failed to pull seed from OCI registry: {msg}",
                next_action=(
                    "Run `oras login <registry>`,"
                    " verify read permissions,"
                    " and confirm the artifact"
                    " reference exists."
                ),
            )

        tmp_path = Path(tmp)
        sbd_files = sorted(
            p
            for p in tmp_path.rglob("*")
            if p.is_file() and p.suffix.lower() == ".sbd"
        )
        if len(sbd_files) != 1:
            found = (
                ", ".join(
                    str(p.relative_to(tmp_path))
                    for p in sbd_files
                )
                or "none"
            )
            raise ExternalToolError(
                "Pulled OCI artifact does not"
                " contain exactly one"
                " `.sbd` payload "
                f"(found: {found}).",
                next_action=(
                    "Push a single Seedbraid seed payload with media type "
                    f"`{SB_OCI_SEED_MEDIA_TYPE}` and retry pull."
                ),
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(sbd_files[0].read_bytes())

    return out_path
