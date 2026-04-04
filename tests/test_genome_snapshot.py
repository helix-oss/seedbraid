from __future__ import annotations

from pathlib import Path

import pytest

from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import (
    decode_file,
    encode_file,
    restore_genome,
    snapshot_genome,
    verify_seed,
)
from seedbraid.errors import (
    ACTION_VERIFY_SNAPSHOT,
    SeedbraidError,
)
from seedbraid.storage import open_genome


def test_genome_snapshot_restore_supports_decode(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
    snapshot = tmp_path / "genome.sgs"
    out = tmp_path / "decoded.bin"

    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src.write_bytes((b"snapshot-restore-" * 20_000) + bytes(range(255)))
    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    encode_file(
        in_path=src,
        genome_path=genome_a,
        out_seed_path=seed,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    snap_stats = snapshot_genome(genome_a, snapshot)
    assert snap_stats["chunks"] > 0

    restore_stats = restore_genome(snapshot, genome_b, replace=False)
    assert restore_stats["inserted"] > 0

    decode_file(seed, genome_b, out)
    assert out.read_bytes() == src.read_bytes()

    report = verify_seed(seed, genome_b, strict=True)
    assert report.ok


def test_genome_restore_replace_overwrites_existing_content(
    tmp_path: Path,
) -> None:
    src_a = tmp_path / "a.bin"
    src_b = tmp_path / "b.bin"
    snapshot = tmp_path / "genome.sgs"
    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src_a.write_bytes((b"A" * 200_000) + b"tail-a")
    src_b.write_bytes((b"B" * 200_000) + b"tail-b")

    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    encode_file(
        in_path=src_a,
        genome_path=genome_a,
        out_seed_path=tmp_path / "a.sbd",
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )
    encode_file(
        in_path=src_b,
        genome_path=genome_b,
        out_seed_path=tmp_path / "b.sbd",
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    with open_genome(genome_a) as source:
        expected_count = source.count_chunks()
    snapshot_genome(genome_a, snapshot)
    restore_genome(snapshot, genome_b, replace=True)

    with open_genome(genome_b) as restored:
        assert restored.count_chunks() == expected_count


def test_restore_rejects_corrupted_snapshot_chunk(
    tmp_path: Path,
) -> None:
    """Corrupted snapshot payload triggers hash mismatch."""
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
    snapshot = tmp_path / "genome.sgs"
    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src.write_bytes(
        (b"snap-corrupt-" * 20_000)
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
        genome_path=genome_a,
        out_seed_path=seed,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )
    snapshot_genome(genome_a, snapshot)

    # Corrupt a payload in the snapshot binary
    raw = bytearray(snapshot.read_bytes())
    # Header = SGS1(4) + version(4) + count(4) = 12
    # First entry = hash(32) + size(4) + payload(size)
    # Corrupt the first byte of the payload
    payload_offset = 12 + 32 + 4
    raw[payload_offset] ^= 0xFF
    snapshot.write_bytes(bytes(raw))

    with pytest.raises(
        SeedbraidError, match="hash mismatch",
    ):
        restore_genome(
            snapshot, genome_b, replace=False,
        )


def test_restore_bad_magic_has_next_action(
    tmp_path: Path,
) -> None:
    bad_snap = tmp_path / "bad.sgs"
    bad_snap.write_bytes(b"XXXX" + b"\x00" * 10)
    with pytest.raises(SeedbraidError) as exc_info:
        restore_genome(
            bad_snap, tmp_path / "genome",
            replace=False,
        )
    assert (
        exc_info.value.next_action
        == ACTION_VERIFY_SNAPSHOT
    )
