"""Chunk CID sidecar manifest (.sbd.chunks.json).

Manages the JSON manifest that maps chunk SHA-256
digests to IPFS CIDv1 identifiers for distributed
chunk storage workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    ACTION_REGENERATE_MANIFEST,
    SeedbraidError,
)

__all__ = [
    "MANIFEST_FORMAT",
    "MANIFEST_VERSION",
    "ChunkEntry",
    "ChunkManifest",
    "manifest_path_for_seed",
    "read_chunk_manifest",
    "write_chunk_manifest",
]

MANIFEST_FORMAT = "SBD1-CHUNKS"
MANIFEST_VERSION = 1


@dataclass(frozen=True)
class ChunkEntry:
    """Single chunk mapping in the manifest."""

    hash_hex: str
    cid: str


@dataclass(frozen=True)
class ChunkManifest:
    """Complete chunk CID manifest."""

    format: str = MANIFEST_FORMAT
    version: int = MANIFEST_VERSION
    seed_sha256: str = ""
    chunks: tuple[ChunkEntry, ...] = ()
    dag_root_cid: str | None = None


def manifest_path_for_seed(
    seed_path: Path,
) -> Path:
    """Derive sidecar path from seed path.

    Convention: ``<seed>.sbd.chunks.json``

    >>> manifest_path_for_seed(Path("data.sbd"))
    PosixPath('data.sbd.chunks.json')
    """
    return seed_path.with_suffix(
        seed_path.suffix + ".chunks.json",
    )


def write_chunk_manifest(
    manifest: ChunkManifest,
    path: Path,
) -> None:
    """Write manifest to JSON sidecar file.

    Creates parent directories if they do not exist.
    Output is compact JSON with sorted keys for
    deterministic byte-identical output.

    Args:
        manifest: The manifest to serialize.
        path: Destination file path.
    """
    data = {
        "format": manifest.format,
        "version": manifest.version,
        "seed_sha256": manifest.seed_sha256,
        "chunks": [
            {"hash": e.hash_hex, "cid": e.cid}
            for e in manifest.chunks
        ],
        "dag_root_cid": manifest.dag_root_cid,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def read_chunk_manifest(
    path: Path,
) -> ChunkManifest:
    """Read and validate manifest from JSON file.

    Args:
        path: Path to the sidecar JSON file.

    Returns:
        Parsed and validated ``ChunkManifest``.

    Raises:
        SeedbraidError: If the file cannot be read,
            JSON is malformed, or required fields are
            missing or invalid
            (code ``SB_E_CHUNK_MANIFEST_FORMAT``).
    """
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise SeedbraidError(
            f"Cannot read chunk manifest: {exc}",
            code="SB_E_CHUNK_MANIFEST_FORMAT",
            next_action=ACTION_REGENERATE_MANIFEST,
        ) from exc

    if not isinstance(raw, dict):
        raise SeedbraidError(
            "Chunk manifest root must be a"
            " JSON object",
            code="SB_E_CHUNK_MANIFEST_FORMAT",
            next_action=ACTION_REGENERATE_MANIFEST,
        )

    fmt = raw.get("format")
    if fmt != MANIFEST_FORMAT:
        raise SeedbraidError(
            "Unknown manifest format:"
            f" {fmt!r}",
            code="SB_E_CHUNK_MANIFEST_FORMAT",
            next_action=ACTION_REGENERATE_MANIFEST,
        )

    ver = raw.get("version")
    if ver != MANIFEST_VERSION:
        raise SeedbraidError(
            "Unsupported manifest version:"
            f" {ver!r}",
            code="SB_E_CHUNK_MANIFEST_FORMAT",
            next_action=ACTION_REGENERATE_MANIFEST,
        )

    raw_chunks = raw.get("chunks")
    if not isinstance(raw_chunks, list):
        raise SeedbraidError(
            "Manifest 'chunks' must be an array",
            code="SB_E_CHUNK_MANIFEST_FORMAT",
            next_action=ACTION_REGENERATE_MANIFEST,
        )

    entries: list[ChunkEntry] = []
    for i, item in enumerate(raw_chunks):
        if not isinstance(item, dict):
            raise SeedbraidError(
                f"Chunk entry {i} must be"
                " an object",
                code="SB_E_CHUNK_MANIFEST_FORMAT",
                next_action=(
                    ACTION_REGENERATE_MANIFEST
                ),
            )
        h = item.get("hash")
        c = item.get("cid")
        if (
            not isinstance(h, str)
            or not isinstance(c, str)
        ):
            raise SeedbraidError(
                f"Chunk entry {i} missing"
                " 'hash' or 'cid' string",
                code="SB_E_CHUNK_MANIFEST_FORMAT",
                next_action=(
                    ACTION_REGENERATE_MANIFEST
                ),
            )
        entries.append(ChunkEntry(
            hash_hex=h,
            cid=c,
        ))

    return ChunkManifest(
        format=fmt,
        version=ver,
        seed_sha256=raw.get("seed_sha256", ""),
        chunks=tuple(entries),
        dag_root_cid=raw.get("dag_root_cid"),
    )
