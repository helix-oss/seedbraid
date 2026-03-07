"""High-level encode, decode, verify, and genome management operations.

Orchestrates chunking, genome storage, and HLX1 seed container I/O
to implement the core Helix file reconstruction workflow.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any

from .chunking import ChunkerConfig, iter_chunks
from .container import (
    OP_RAW,
    OP_REF,
    Recipe,
    RecipeOp,
    Seed,
    read_seed,
    verify_signature,
    write_seed,
)
from .errors import (
    ACTION_CHECK_DISK,
    ACTION_CHECK_GENOME,
    ACTION_ENABLE_LEARN_OR_PORTABLE,
    ACTION_REFETCH_SEED,
    ACTION_REGENERATE_SEED,
    ACTION_UPGRADE_HELIX,
    ACTION_VERIFY_GENES_PACK,
    ACTION_VERIFY_SNAPSHOT,
    DecodeError,
    HelixError,
)
from .storage import GenomeStorage, open_genome

GENES_MAGIC = b"GENE1"
GENOME_SNAPSHOT_MAGIC = b"HGS1"
GENOME_SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class EncodeStats:
    total_chunks: int
    reused_chunks: int
    new_chunks: int
    raw_chunks: int
    unique_hashes: int


@dataclass(frozen=True)
class VerifyReport:
    ok: bool
    missing_hashes: list[str]
    missing_count: int
    expected_sha256: str | None
    actual_sha256: str | None
    reason: str | None


def _sha256_bytes(data: bytes) -> bytes:
    h = hashlib.sha256()
    h.update(data)
    return h.digest()


def sha256_file(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Reads the file in streaming 1 MiB blocks to
    avoid loading the entire file into memory.

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest string.
    """
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _chunk_stream_from_file(
    path: str | Path, chunker: str, cfg: ChunkerConfig,
) -> Iterator[bytes]:
    with Path(path).open("rb") as f:
        yield from iter_chunks(f, chunker, cfg)


def _build_chunk_index(
    in_path: Path,
    genome: GenomeStorage,
    chunker: str,
    cfg: ChunkerConfig,
    learn: bool,
    portable: bool,
) -> tuple[
    list[bytes], list[RecipeOp],
    dict[int, bytes], EncodeStats,
]:
    hash_to_index: dict[bytes, int] = {}
    hash_table: list[bytes] = []
    ops: list[RecipeOp] = []
    raw_payloads: dict[int, bytes] = {}

    total_chunks = 0
    reused_chunks = 0
    new_chunks = 0
    raw_chunks = 0

    for chunk in _chunk_stream_from_file(
        in_path, chunker, cfg,
    ):
        total_chunks += 1
        digest = _sha256_bytes(chunk)

        index = hash_to_index.get(digest)
        if index is None:
            index = len(hash_table)
            hash_to_index[digest] = index
            hash_table.append(digest)

        known = genome.has_chunk(digest)
        if known:
            reused_chunks += 1
            ops.append(
                RecipeOp(
                    opcode=OP_REF,
                    hash_index=index,
                ),
            )
            continue

        new_chunks += 1
        if learn:
            genome.put_chunk(digest, chunk)

        if portable:
            raw_payloads[index] = chunk
            raw_chunks += 1
            ops.append(
                RecipeOp(
                    opcode=OP_RAW,
                    hash_index=index,
                ),
            )
        elif learn:
            ops.append(
                RecipeOp(
                    opcode=OP_REF,
                    hash_index=index,
                ),
            )
        else:
            raise HelixError(
                "Encountered unknown chunk while"
                " --no-learn and --no-portable"
                " are active."
                " Enable --learn or --portable.",
                next_action=(
                    ACTION_ENABLE_LEARN_OR_PORTABLE
                ),
            )

    stats = EncodeStats(
        total_chunks=total_chunks,
        reused_chunks=reused_chunks,
        new_chunks=new_chunks,
        raw_chunks=raw_chunks,
        unique_hashes=len(hash_table),
    )
    return hash_table, ops, raw_payloads, stats


def _build_manifest(
    in_path: Path,
    chunker: str,
    cfg: ChunkerConfig,
    stats: EncodeStats,
    portable: bool,
    learn: bool,
    manifest_private: bool,
) -> dict[str, Any]:
    if manifest_private:
        return {
            "format": "HLX1",
            "version": 1,
            "manifest_private": True,
            "source_size": None,
            "source_sha256": None,
            "chunker": {"name": chunker},
            "portable": portable,
            "learn": learn,
        }
    return {
        "format": "HLX1",
        "version": 1,
        "manifest_private": False,
        "source_size": in_path.stat().st_size,
        "source_sha256": sha256_file(in_path),
        "chunker": {
            "name": chunker,
            "min": cfg.min_size,
            "avg": cfg.avg_size,
            "max": cfg.max_size,
            "window_size": cfg.window_size,
        },
        "portable": portable,
        "learn": learn,
        "stats": {
            "total_chunks": stats.total_chunks,
            "reused_chunks": stats.reused_chunks,
            "new_chunks": stats.new_chunks,
            "raw_chunks": stats.raw_chunks,
            "unique_hashes": stats.unique_hashes,
        },
        "created_at": (
            dt.datetime.now(dt.UTC).isoformat()
        ),
    }


def encode_file(
    in_path: str | Path,
    genome_path: str | Path,
    out_seed_path: str | Path,
    *,
    chunker: str,
    cfg: ChunkerConfig,
    learn: bool,
    portable: bool,
    manifest_compression: str,
    encryption_key: str | None = None,
    manifest_private: bool = False,
) -> EncodeStats:
    """Encode a file into an HLX1 seed using the genome.

    Chunks the input file, stores new chunks in the
    genome when ``learn=True``, and writes the binary
    seed to ``out_seed_path``.

    Args:
        in_path: Path to the source file to encode.
        genome_path: Path to the genome directory or
            SQLite file.
        out_seed_path: Destination path for the
            ``.hlx`` seed output.
        chunker: Algorithm name.  One of
            ``"fixed"``, ``"cdc_buzhash"``,
            ``"cdc_rabin"``.
        cfg: CDC parameters (min/avg/max chunk sizes
            and window size).
        learn: Store new chunks in the genome during
            encode.
        portable: Embed unknown chunks as RAW
            payloads in the seed.
        manifest_compression: Compression for the
            manifest section.  One of ``"none"``,
            ``"zlib"``, ``"zstd"``.
        encryption_key: Passphrase to wrap the seed
            in HLE1 encryption.  ``None`` disables
            encryption.
        manifest_private: Omit source path, size,
            and SHA-256 from the manifest.

    Returns:
        Encode statistics with chunk counts and
        dedup metrics.

    Raises:
        HelixError: If an unknown chunk is found
            while both ``learn`` and ``portable``
            are ``False``.
        SeedFormatError: If the manifest compression
            is unsupported.
    """
    in_path = Path(in_path)

    with open_genome(genome_path) as genome:
        hash_table, ops, raw_payloads, stats = (
            _build_chunk_index(
                in_path, genome,
                chunker, cfg, learn, portable,
            )
        )
        manifest = _build_manifest(
            in_path, chunker, cfg, stats,
            portable, learn, manifest_private,
        )
        recipe = Recipe(
            hash_table=hash_table, ops=ops,
        )
        write_seed(
            out_seed_path,
            manifest,
            recipe,
            raw_payloads,
            manifest_compression,
            encryption_key=encryption_key,
        )
        return stats


def _resolve_chunk(
    op: RecipeOp,
    hash_table: list[bytes],
    raw_payloads: dict[int, bytes],
    genome: GenomeStorage,
) -> bytes:
    if op.hash_index >= len(hash_table):
        raise DecodeError(
            "Recipe refers to hash index out of bounds.",
            next_action=ACTION_REGENERATE_SEED,
        )
    digest = hash_table[op.hash_index]

    if op.opcode == OP_REF:
        chunk = genome.get_chunk(digest)
        if chunk is not None:
            return chunk
        chunk = raw_payloads.get(op.hash_index)
        if chunk is not None:
            return chunk
        raise DecodeError(
            f"Missing required chunk: {digest.hex()}",
            next_action=ACTION_CHECK_GENOME,
        )

    chunk = raw_payloads.get(op.hash_index)
    if chunk is not None:
        return chunk
    chunk = genome.get_chunk(digest)
    if chunk is not None:
        return chunk
    raise DecodeError(
        f"Missing RAW payload and genome chunk: {digest.hex()}",
        next_action=ACTION_CHECK_GENOME,
    )


def decode_file(
    seed_path: str | Path,
    genome_path: str | Path,
    out_path: str | Path,
    *,
    encryption_key: str | None = None,
) -> str:
    """Reconstruct a file from an HLX1 seed.

    Resolves each chunk from the genome or embedded
    RAW payloads, writes the reassembled file, and
    verifies the SHA-256 digest against the manifest.

    Args:
        seed_path: Path to the ``.hlx`` seed file.
        genome_path: Path to the genome directory or
            SQLite file.
        out_path: Destination path for the
            reconstructed file.
        encryption_key: Passphrase to decrypt the
            seed if encrypted.

    Returns:
        Lowercase hex SHA-256 digest of the decoded
        file.

    Raises:
        DecodeError: If a required chunk is missing
            or the reconstructed hash does not match
            the manifest.
    """
    seed = read_seed(
        seed_path, encryption_key=encryption_key,
    )
    out_path = Path(out_path)
    h = hashlib.sha256()

    with open_genome(genome_path) as genome:
        with out_path.open("wb") as out:
            for op in seed.recipe.ops:
                chunk = _resolve_chunk(
                    op,
                    seed.recipe.hash_table,
                    seed.raw_payloads,
                    genome,
                )
                out.write(chunk)
                h.update(chunk)

    actual = h.hexdigest()
    expected = seed.manifest.get("source_sha256")
    if expected and expected != actual:
        raise DecodeError(
            "Decoded SHA-256 mismatch: "
            f"expected {expected}, got {actual}.",
            next_action=ACTION_REFETCH_SEED,
        )
    return actual


def _fail_report(
    reason: str | None,
    expected_sha256: str | None = None,
    actual_sha256: str | None = None,
) -> VerifyReport:
    return VerifyReport(
        ok=False,
        missing_hashes=[],
        missing_count=0,
        expected_sha256=expected_sha256,
        actual_sha256=actual_sha256,
        reason=reason,
    )


def _verify_signature_phase(
    seed: Seed,
    require_signature: bool,
    signature_key: str | None,
    expected_sha256: str | None,
) -> VerifyReport | None:
    if require_signature and seed.signature is None:
        return _fail_report(
            "Signature is required but missing.",
            expected_sha256=expected_sha256,
        )
    if seed.signature is not None:
        if signature_key is None:
            if require_signature:
                return _fail_report(
                    "Signature key is required"
                    " to verify signed seed.",
                    expected_sha256=expected_sha256,
                )
        else:
            ok, sig_reason = verify_signature(
                seed, signature_key,
            )
            if not ok:
                return _fail_report(
                    sig_reason,
                    expected_sha256=expected_sha256,
                )
    return None


def _check_chunk_availability(
    seed: Seed,
    genome: GenomeStorage,
    expected_sha256: str | None,
) -> VerifyReport | None:
    missing: list[str] = []
    ht_len = len(seed.recipe.hash_table)
    for op in seed.recipe.ops:
        if op.hash_index >= ht_len:
            return _fail_report(
                "Recipe index out of bounds.",
                expected_sha256=expected_sha256,
            )
        digest = seed.recipe.hash_table[op.hash_index]
        has_raw = op.hash_index in seed.raw_payloads
        if not (has_raw or genome.has_chunk(digest)):
            missing.append(digest.hex())

    if missing:
        unique_missing = sorted(set(missing))
        return VerifyReport(
            ok=False,
            missing_hashes=unique_missing,
            missing_count=len(unique_missing),
            expected_sha256=expected_sha256,
            actual_sha256=None,
            reason="Missing required chunks.",
        )
    return None


def _strict_reconstruct(
    seed: Seed,
    genome: GenomeStorage,
    expected_size: int | None,
    expected_sha256: str | None,
) -> VerifyReport:
    h = hashlib.sha256()
    actual_size = 0
    for op in seed.recipe.ops:
        chunk = _resolve_chunk(
            op,
            seed.recipe.hash_table,
            seed.raw_payloads,
            genome,
        )
        h.update(chunk)
        actual_size += len(chunk)

    if (
        isinstance(expected_size, int)
        and expected_size != actual_size
    ):
        return _fail_report(
            "Reconstructed size mismatch: "
            f"expected {expected_size},"
            f" got {actual_size}.",
            expected_sha256=expected_sha256,
        )

    actual = h.hexdigest()
    if expected_sha256 and expected_sha256 != actual:
        return _fail_report(
            "Reconstructed SHA-256 mismatch.",
            expected_sha256=expected_sha256,
            actual_sha256=actual,
        )

    return VerifyReport(
        ok=True,
        missing_hashes=[],
        missing_count=0,
        expected_sha256=expected_sha256,
        actual_sha256=actual,
        reason=None,
    )


def verify_seed(
    seed_path: str | Path,
    genome_path: str | Path,
    *,
    strict: bool = False,
    require_signature: bool = False,
    signature_key: str | None = None,
    encryption_key: str | None = None,
) -> VerifyReport:
    """Verify a seed against the genome.

    In default mode, checks chunk availability only.
    In ``strict`` mode, fully reconstructs the file
    in memory and verifies the SHA-256 digest.

    Args:
        seed_path: Path to the ``.hlx`` seed file.
        genome_path: Path to the genome directory or
            SQLite file.
        strict: Reconstruct and hash-verify the full
            file instead of just checking chunk
            availability.
        require_signature: Fail if the seed has no
            signature section.
        signature_key: HMAC key to verify the
            signature.  ``None`` skips verification
            unless ``require_signature`` is set.
        encryption_key: Passphrase to decrypt the
            seed if encrypted.

    Returns:
        Verification report with ``ok`` status,
        missing hashes, and optional SHA-256
        digests.
    """
    seed = read_seed(
        seed_path, encryption_key=encryption_key,
    )
    expected = seed.manifest.get("source_sha256")
    expected_size = seed.manifest.get("source_size")

    with open_genome(genome_path) as genome:
        sig_result = _verify_signature_phase(
            seed, require_signature,
            signature_key, expected,
        )
        if sig_result is not None:
            return sig_result

        chunk_result = _check_chunk_availability(
            seed, genome, expected,
        )
        if chunk_result is not None:
            return chunk_result

        if not strict:
            return VerifyReport(
                ok=True,
                missing_hashes=[],
                missing_count=0,
                expected_sha256=expected,
                actual_sha256=None,
                reason=None,
            )

        return _strict_reconstruct(
            seed, genome, expected_size, expected,
        )


def _expand_input_paths(
    dir_or_glob: str | Path,
) -> list[Path]:
    p = Path(dir_or_glob)
    if p.is_dir():
        return [
            x for x in sorted(p.rglob("*"))
            if x.is_file()
        ]
    matches = [
        Path(x)
        for x in sorted(glob(str(dir_or_glob), recursive=True))
    ]
    return [x for x in matches if x.is_file()]


def prime_genome(
    dir_or_glob: str | Path,
    genome_path: str | Path,
    *,
    chunker: str,
    cfg: ChunkerConfig,
) -> dict[str, int]:
    """Learn chunks from files into the genome.

    Accepts a directory path (recursively scanned)
    or a glob pattern.  Each file is chunked and new
    chunks are stored in the genome.

    Args:
        dir_or_glob: Directory path or glob pattern
            for input files.
        genome_path: Path to the genome directory or
            SQLite file.
        chunker: Chunking algorithm name.
        cfg: Chunker parameters.

    Returns:
        Dict with keys ``"files"``,
        ``"total_chunks"``, ``"new_chunks"``,
        ``"reused_chunks"``, and
        ``"dedup_ratio_bps"`` (basis points).
    """
    total_chunks = 0
    new_chunks = 0

    with open_genome(genome_path) as genome:
        files = _expand_input_paths(dir_or_glob)
        for file_path in files:
            for chunk in _chunk_stream_from_file(
                file_path, chunker, cfg,
            ):
                total_chunks += 1
                digest = _sha256_bytes(chunk)
                if genome.put_chunk(digest, chunk):
                    new_chunks += 1

        if total_chunks == 0:
            dedup_ratio = 0
        else:
            reused = total_chunks - new_chunks
            dedup_ratio = int(
                (reused / total_chunks) * 10_000
            )
        return {
            "files": len(files),
            "total_chunks": total_chunks,
            "new_chunks": new_chunks,
            "reused_chunks": total_chunks - new_chunks,
            "dedup_ratio_bps": dedup_ratio,
        }


def snapshot_genome(
    genome_path: str | Path,
    out_path: str | Path,
) -> dict[str, int]:
    """Export the genome to an HGS1 binary snapshot.

    Writes all chunks to a portable binary file that
    can be restored on another machine.

    Args:
        genome_path: Path to the genome directory or
            SQLite file.
        out_path: Destination path for the snapshot
            file.

    Returns:
        Dict with keys ``"chunks"`` and ``"bytes"``
        indicating the number of chunks and total
        payload bytes exported.

    Raises:
        HelixError: If writing to ``out_path`` fails.
    """
    out_path = Path(out_path)
    total_chunks = 0
    total_bytes = 0

    with open_genome(genome_path) as genome:
        chunk_count = genome.count_chunks()
        try:
            with out_path.open("wb") as out:
                out.write(
                    struct.pack(
                        ">4sHQ",
                        GENOME_SNAPSHOT_MAGIC,
                        GENOME_SNAPSHOT_VERSION,
                        chunk_count,
                    )
                )
                for chunk_hash, payload in genome.iter_chunks():
                    out.write(struct.pack(">32sI", chunk_hash, len(payload)))
                    out.write(payload)
                    total_chunks += 1
                    total_bytes += len(payload)
        except OSError as exc:
            raise HelixError(
                "Failed to write genome snapshot:"
                f" {out_path}",
                next_action=ACTION_CHECK_DISK,
            ) from exc

    return {"chunks": total_chunks, "bytes": total_bytes}


def restore_genome(
    snapshot_path: str | Path,
    genome_path: str | Path,
    *,
    replace: bool,
) -> dict[str, int]:
    """Restore a genome from an HGS1 snapshot.

    When ``replace`` is ``True``, all existing chunks
    are deleted before import.

    Args:
        snapshot_path: Path to the HGS1 snapshot
            file.
        genome_path: Path to the genome directory or
            SQLite file.
        replace: Delete all existing chunks before
            restoring.

    Returns:
        Dict with keys ``"inserted"``,
        ``"skipped"``, and ``"entries"``.

    Raises:
        HelixError: If the snapshot is truncated,
            has an invalid magic or version, or
            reading fails.
    """
    snapshot_path = Path(snapshot_path)
    inserted = 0
    skipped = 0
    chunk_count = 0

    with open_genome(genome_path) as genome:
        try:
            with snapshot_path.open("rb") as inp:
                header = inp.read(14)
                if len(header) != 14:
                    raise HelixError(
                        "Invalid genome snapshot:"
                        " header is truncated.",
                        next_action=ACTION_VERIFY_SNAPSHOT,
                    )
                magic, version, chunk_count = struct.unpack(">4sHQ", header)
                if magic != GENOME_SNAPSHOT_MAGIC:
                    raise HelixError(
                        "Invalid genome snapshot"
                        " magic. Expected HGS1.",
                        next_action=ACTION_VERIFY_SNAPSHOT,
                    )
                if version != GENOME_SNAPSHOT_VERSION:
                    raise HelixError(
                        "Unsupported genome snapshot"
                        f" version: {version}.",
                        next_action=ACTION_UPGRADE_HELIX,
                    )

                if replace:
                    genome.clear_chunks()

                for _ in range(chunk_count):
                    entry_header = inp.read(36)
                    if len(entry_header) != 36:
                        raise HelixError(
                            "Invalid genome snapshot:"
                            " entry header is"
                            " truncated.",
                            next_action=ACTION_VERIFY_SNAPSHOT,
                        )
                    chunk_hash, size = struct.unpack(">32sI", entry_header)
                    payload = inp.read(size)
                    if len(payload) != size:
                        raise HelixError(
                            "Invalid genome snapshot:"
                            " entry payload is"
                            " truncated.",
                            next_action=ACTION_VERIFY_SNAPSHOT,
                        )
                    if genome.put_chunk(chunk_hash, payload):
                        inserted += 1
                    else:
                        skipped += 1

                trailing = inp.read(1)
                if trailing:
                    raise HelixError(
                        "Invalid genome snapshot:"
                        " trailing bytes found.",
                        next_action=ACTION_VERIFY_SNAPSHOT,
                    )
        except OSError as exc:
            raise HelixError(
                "Failed to read genome snapshot:"
                f" {snapshot_path}",
                next_action=ACTION_CHECK_DISK,
            ) from exc

    return {
        "inserted": inserted,
        "skipped": skipped,
        "entries": int(chunk_count),
    }


def export_genes(
    seed_path: str | Path,
    genome_path: str | Path,
    out_path: str | Path,
) -> dict[str, int]:
    """Export seed-dependent chunks to a GENE1 pack.

    Writes chunks referenced by the seed's hash
    table.  Missing chunks are written as zero-length
    entries and counted separately.

    Args:
        seed_path: Path to the ``.hlx`` seed file.
        genome_path: Path to the genome directory or
            SQLite file.
        out_path: Destination path for the GENE1
            pack file.

    Returns:
        Dict with keys ``"total"``, ``"exported"``,
        and ``"missing"``.
    """
    seed = read_seed(seed_path)
    out_path = Path(out_path)
    exported = 0
    missing = 0

    with open_genome(genome_path) as genome:
        with out_path.open("wb") as out:
            out.write(GENES_MAGIC)
            out.write(len(seed.recipe.hash_table).to_bytes(4, "big"))
            for digest in seed.recipe.hash_table:
                chunk = genome.get_chunk(digest)
                if chunk is None:
                    missing += 1
                    out.write(digest)
                    out.write((0).to_bytes(4, "big"))
                    continue
                exported += 1
                out.write(digest)
                out.write(len(chunk).to_bytes(4, "big"))
                out.write(chunk)

    return {
        "total": len(seed.recipe.hash_table),
        "exported": exported,
        "missing": missing,
    }


def import_genes(
    pack_path: str | Path,
    genome_path: str | Path,
) -> dict[str, int]:
    """Import chunks from a GENE1 pack into the genome.

    Zero-length entries in the pack are skipped.

    Args:
        pack_path: Path to the GENE1 pack file.
        genome_path: Path to the genome directory or
            SQLite file.

    Returns:
        Dict with keys ``"inserted"`` and
        ``"skipped"``.

    Raises:
        HelixError: If the pack magic is invalid or
            the file is truncated.
    """
    pack_path = Path(pack_path)
    inserted = 0
    skipped = 0

    with open_genome(genome_path) as genome:
        with pack_path.open("rb") as inp:
            magic = inp.read(len(GENES_MAGIC))
            if magic != GENES_MAGIC:
                raise HelixError(
                    "Invalid genes pack magic."
                    " Expected GENE1.",
                    next_action=ACTION_VERIFY_GENES_PACK,
                )
            count = int.from_bytes(inp.read(4), "big")
            for _ in range(count):
                digest = inp.read(32)
                if len(digest) != 32:
                    raise HelixError(
                        "Truncated genes pack hash entry.",
                        next_action=ACTION_VERIFY_GENES_PACK,
                    )
                size = int.from_bytes(inp.read(4), "big")
                chunk = inp.read(size)
                if len(chunk) != size:
                    raise HelixError(
                        "Truncated genes pack"
                        " payload entry.",
                        next_action=ACTION_VERIFY_GENES_PACK,
                    )
                if size == 0:
                    skipped += 1
                    continue
                if genome.put_chunk(digest, chunk):
                    inserted += 1
                else:
                    skipped += 1

    return {"inserted": inserted, "skipped": skipped}
