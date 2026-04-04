from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import decode_file, encode_file, sha256_file
from seedbraid.errors import DecodeError


def test_roundtrip_bit_perfect(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    out = tmp_path / "decoded.bin"
    seed = tmp_path / "seed.sbd"
    genome = tmp_path / "genome"

    payload = (b"abcdefghij" * 50_000) + bytes(range(256)) * 500
    src.write_bytes(payload)

    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )
    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=seed,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    decode_file(seed, genome, out)
    assert sha256_file(src) == sha256_file(out)


def test_decode_detects_corrupted_genome_chunk(
    tmp_path: Path,
) -> None:
    """Corrupted genome chunk triggers DecodeError."""
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
    out = tmp_path / "decoded.bin"
    genome = tmp_path / "genome"

    src.write_bytes(
        (b"integrity-check-" * 20_000)
        + bytes(range(255))
    )
    cfg = ChunkerConfig(
        min_size=1024,
        avg_size=4096,
        max_size=16384,
        window_size=32,
    )
    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=seed,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    # Corrupt a chunk in the SQLite genome DB
    db_path = genome / "genome.sqlite"
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "SELECT hash, data FROM chunks LIMIT 1",
    )
    chunk_hash, data = cur.fetchone()
    corrupted = b"\x00" * len(data)
    conn.execute(
        "UPDATE chunks SET data=? WHERE hash=?",
        (corrupted, chunk_hash),
    )
    conn.commit()
    conn.close()

    with pytest.raises(
        DecodeError, match="hash mismatch",
    ):
        decode_file(seed, genome, out)
