from __future__ import annotations

import datetime as dt
import hashlib
import struct
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from .chunking import ChunkerConfig, iter_chunks
from .container import OP_RAW, OP_REF, Recipe, RecipeOp, read_seed, verify_signature, write_seed
from .errors import DecodeError, HelixError
from .storage import open_genome

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
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _chunk_stream_from_file(path: str | Path, chunker: str, cfg: ChunkerConfig):
    with Path(path).open("rb") as f:
        yield from iter_chunks(f, chunker, cfg)


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
    in_path = Path(in_path)
    genome = open_genome(genome_path)

    hash_to_index: dict[bytes, int] = {}
    hash_table: list[bytes] = []
    ops: list[RecipeOp] = []
    raw_payloads: dict[int, bytes] = {}

    total_chunks = 0
    reused_chunks = 0
    new_chunks = 0
    raw_chunks = 0

    try:
        for chunk in _chunk_stream_from_file(in_path, chunker, cfg):
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
                ops.append(RecipeOp(opcode=OP_REF, hash_index=index))
                continue

            new_chunks += 1
            if learn:
                genome.put_chunk(digest, chunk)

            if portable:
                raw_payloads[index] = chunk
                raw_chunks += 1
                ops.append(RecipeOp(opcode=OP_RAW, hash_index=index))
            elif learn:
                ops.append(RecipeOp(opcode=OP_REF, hash_index=index))
            else:
                raise HelixError(
                    "Encountered unknown chunk while --no-learn and --no-portable are active. "
                    "Enable --learn or --portable."
                )

        stats = EncodeStats(
            total_chunks=total_chunks,
            reused_chunks=reused_chunks,
            new_chunks=new_chunks,
            raw_chunks=raw_chunks,
            unique_hashes=len(hash_table),
        )
        if manifest_private:
            manifest = {
                "format": "HLX1",
                "version": 1,
                "manifest_private": True,
                "source_size": None,
                "source_sha256": None,
                "chunker": {"name": chunker},
                "portable": portable,
                "learn": learn,
            }
        else:
            manifest = {
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
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
            }
        recipe = Recipe(hash_table=hash_table, ops=ops)
        write_seed(
            out_seed_path,
            manifest,
            recipe,
            raw_payloads,
            manifest_compression,
            encryption_key=encryption_key,
        )
        return stats
    finally:
        genome.close()


def _resolve_chunk(
    op: RecipeOp,
    hash_table: list[bytes],
    raw_payloads: dict[int, bytes],
    genome,
) -> bytes:
    if op.hash_index >= len(hash_table):
        raise DecodeError("Recipe refers to hash index out of bounds.")
    digest = hash_table[op.hash_index]

    if op.opcode == OP_REF:
        chunk = genome.get_chunk(digest)
        if chunk is not None:
            return chunk
        chunk = raw_payloads.get(op.hash_index)
        if chunk is not None:
            return chunk
        raise DecodeError(f"Missing required chunk: {digest.hex()}")

    chunk = raw_payloads.get(op.hash_index)
    if chunk is not None:
        return chunk
    chunk = genome.get_chunk(digest)
    if chunk is not None:
        return chunk
    raise DecodeError(f"Missing RAW payload and genome chunk: {digest.hex()}")


def decode_file(
    seed_path: str | Path,
    genome_path: str | Path,
    out_path: str | Path,
    *,
    encryption_key: str | None = None,
) -> str:
    seed = read_seed(seed_path, encryption_key=encryption_key)
    genome = open_genome(genome_path)
    out_path = Path(out_path)
    h = hashlib.sha256()

    try:
        with out_path.open("wb") as out:
            for op in seed.recipe.ops:
                chunk = _resolve_chunk(op, seed.recipe.hash_table, seed.raw_payloads, genome)
                out.write(chunk)
                h.update(chunk)
    finally:
        genome.close()

    actual = h.hexdigest()
    expected = seed.manifest.get("source_sha256")
    if expected and expected != actual:
        raise DecodeError(
            f"Decoded SHA-256 mismatch: expected {expected}, got {actual}."
        )
    return actual


def verify_seed(
    seed_path: str | Path,
    genome_path: str | Path,
    *,
    strict: bool = False,
    require_signature: bool = False,
    signature_key: str | None = None,
    encryption_key: str | None = None,
) -> VerifyReport:
    seed = read_seed(seed_path, encryption_key=encryption_key)
    genome = open_genome(genome_path)
    missing: list[str] = []
    expected = seed.manifest.get("source_sha256")
    expected_size = seed.manifest.get("source_size")

    try:
        if require_signature and seed.signature is None:
            return VerifyReport(
                ok=False,
                missing_hashes=[],
                missing_count=0,
                expected_sha256=expected,
                actual_sha256=None,
                reason="Signature is required but missing.",
            )
        if seed.signature is not None:
            if signature_key is None:
                if require_signature:
                    return VerifyReport(
                        ok=False,
                        missing_hashes=[],
                        missing_count=0,
                        expected_sha256=expected,
                        actual_sha256=None,
                        reason="Signature key is required to verify signed seed.",
                    )
            else:
                ok, sig_reason = verify_signature(seed, signature_key)
                if not ok:
                    return VerifyReport(
                        ok=False,
                        missing_hashes=[],
                        missing_count=0,
                        expected_sha256=expected,
                        actual_sha256=None,
                        reason=sig_reason,
                    )

        for op in seed.recipe.ops:
            if op.hash_index >= len(seed.recipe.hash_table):
                return VerifyReport(
                    ok=False,
                    missing_hashes=[],
                    missing_count=0,
                    expected_sha256=expected,
                    actual_sha256=None,
                    reason="Recipe index out of bounds.",
                )
            digest = seed.recipe.hash_table[op.hash_index]
            has_genome = genome.has_chunk(digest)
            has_raw = op.hash_index in seed.raw_payloads
            if op.opcode == OP_REF and not (has_genome or has_raw):
                missing.append(digest.hex())
            if op.opcode == OP_RAW and not (has_raw or has_genome):
                missing.append(digest.hex())

        if missing:
            unique_missing = sorted(set(missing))
            return VerifyReport(
                ok=False,
                missing_hashes=unique_missing,
                missing_count=len(unique_missing),
                expected_sha256=expected,
                actual_sha256=None,
                reason="Missing required chunks.",
            )

        if not strict:
            return VerifyReport(
                ok=True,
                missing_hashes=[],
                missing_count=0,
                expected_sha256=expected,
                actual_sha256=None,
                reason=None,
            )

        h = hashlib.sha256()
        actual_size = 0
        for op in seed.recipe.ops:
            chunk = _resolve_chunk(op, seed.recipe.hash_table, seed.raw_payloads, genome)
            h.update(chunk)
            actual_size += len(chunk)

        if isinstance(expected_size, int) and expected_size != actual_size:
            return VerifyReport(
                ok=False,
                missing_hashes=[],
                missing_count=0,
                expected_sha256=expected,
                actual_sha256=None,
                reason=(
                    "Reconstructed size mismatch: "
                    f"expected {expected_size}, got {actual_size}."
                ),
            )

        actual = h.hexdigest()
        if expected and expected != actual:
            return VerifyReport(
                ok=False,
                missing_hashes=[],
                missing_count=0,
                expected_sha256=expected,
                actual_sha256=actual,
                reason="Reconstructed SHA-256 mismatch.",
            )

        return VerifyReport(
            ok=True,
            missing_hashes=[],
            missing_count=0,
            expected_sha256=expected,
            actual_sha256=actual,
            reason=None,
        )
    finally:
        genome.close()


def _expand_input_paths(dir_or_glob: str | Path) -> list[Path]:
    p = Path(dir_or_glob)
    if p.is_dir():
        return [x for x in sorted(p.rglob("*")) if x.is_file()]
    matches = [Path(x) for x in sorted(glob(str(dir_or_glob), recursive=True))]
    return [x for x in matches if x.is_file()]


def prime_genome(
    dir_or_glob: str | Path,
    genome_path: str | Path,
    *,
    chunker: str,
    cfg: ChunkerConfig,
) -> dict[str, int]:
    genome = open_genome(genome_path)
    total_chunks = 0
    new_chunks = 0

    try:
        files = _expand_input_paths(dir_or_glob)
        for file_path in files:
            for chunk in _chunk_stream_from_file(file_path, chunker, cfg):
                total_chunks += 1
                digest = _sha256_bytes(chunk)
                if genome.put_chunk(digest, chunk):
                    new_chunks += 1

        if total_chunks == 0:
            dedup_ratio = 0
        else:
            dedup_ratio = int(((total_chunks - new_chunks) / total_chunks) * 10_000)
        return {
            "files": len(files),
            "total_chunks": total_chunks,
            "new_chunks": new_chunks,
            "reused_chunks": total_chunks - new_chunks,
            "dedup_ratio_bps": dedup_ratio,
        }
    finally:
        genome.close()


def snapshot_genome(genome_path: str | Path, out_path: str | Path) -> dict[str, int]:
    genome = open_genome(genome_path)
    out_path = Path(out_path)
    total_chunks = 0
    total_bytes = 0

    try:
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
            raise HelixError(f"Failed to write genome snapshot: {out_path}") from exc
    finally:
        genome.close()

    return {"chunks": total_chunks, "bytes": total_bytes}


def restore_genome(
    snapshot_path: str | Path,
    genome_path: str | Path,
    *,
    replace: bool,
) -> dict[str, int]:
    snapshot_path = Path(snapshot_path)
    genome = open_genome(genome_path)
    inserted = 0
    skipped = 0

    try:
        with snapshot_path.open("rb") as inp:
            header = inp.read(14)
            if len(header) != 14:
                raise HelixError("Invalid genome snapshot: header is truncated.")
            magic, version, chunk_count = struct.unpack(">4sHQ", header)
            if magic != GENOME_SNAPSHOT_MAGIC:
                raise HelixError("Invalid genome snapshot magic. Expected HGS1.")
            if version != GENOME_SNAPSHOT_VERSION:
                raise HelixError(f"Unsupported genome snapshot version: {version}.")

            if replace:
                genome.clear_chunks()

            for _ in range(chunk_count):
                entry_header = inp.read(36)
                if len(entry_header) != 36:
                    raise HelixError("Invalid genome snapshot: entry header is truncated.")
                chunk_hash, size = struct.unpack(">32sI", entry_header)
                payload = inp.read(size)
                if len(payload) != size:
                    raise HelixError("Invalid genome snapshot: entry payload is truncated.")
                if genome.put_chunk(chunk_hash, payload):
                    inserted += 1
                else:
                    skipped += 1

            trailing = inp.read(1)
            if trailing:
                raise HelixError("Invalid genome snapshot: trailing bytes found.")
    except OSError as exc:
        raise HelixError(f"Failed to read genome snapshot: {snapshot_path}") from exc
    finally:
        genome.close()

    return {"inserted": inserted, "skipped": skipped, "entries": int(chunk_count)}


def export_genes(
    seed_path: str | Path,
    genome_path: str | Path,
    out_path: str | Path,
) -> dict[str, int]:
    seed = read_seed(seed_path)
    genome = open_genome(genome_path)
    out_path = Path(out_path)
    exported = 0
    missing = 0

    try:
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
    finally:
        genome.close()

    return {"total": len(seed.recipe.hash_table), "exported": exported, "missing": missing}


def import_genes(pack_path: str | Path, genome_path: str | Path) -> dict[str, int]:
    pack_path = Path(pack_path)
    genome = open_genome(genome_path)
    inserted = 0
    skipped = 0

    try:
        with pack_path.open("rb") as inp:
            magic = inp.read(len(GENES_MAGIC))
            if magic != GENES_MAGIC:
                raise HelixError("Invalid genes pack magic. Expected GENE1.")
            count = int.from_bytes(inp.read(4), "big")
            for _ in range(count):
                digest = inp.read(32)
                if len(digest) != 32:
                    raise HelixError("Truncated genes pack hash entry.")
                size = int.from_bytes(inp.read(4), "big")
                chunk = inp.read(size)
                if len(chunk) != size:
                    raise HelixError("Truncated genes pack payload entry.")
                if size == 0:
                    skipped += 1
                    continue
                if genome.put_chunk(digest, chunk):
                    inserted += 1
                else:
                    skipped += 1
    finally:
        genome.close()

    return {"inserted": inserted, "skipped": skipped}
