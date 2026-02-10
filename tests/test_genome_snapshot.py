from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import decode_file, encode_file, restore_genome, snapshot_genome, verify_seed
from helix.storage import open_genome


def test_genome_snapshot_restore_supports_decode(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    snapshot = tmp_path / "genome.hgs"
    out = tmp_path / "decoded.bin"

    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src.write_bytes((b"snapshot-restore-" * 20_000) + bytes(range(255)))
    cfg = ChunkerConfig(min_size=1024, avg_size=4096, max_size=16384, window_size=32)

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


def test_genome_restore_replace_overwrites_existing_content(tmp_path: Path) -> None:
    src_a = tmp_path / "a.bin"
    src_b = tmp_path / "b.bin"
    snapshot = tmp_path / "genome.hgs"
    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src_a.write_bytes((b"A" * 200_000) + b"tail-a")
    src_b.write_bytes((b"B" * 200_000) + b"tail-b")

    cfg = ChunkerConfig(min_size=1024, avg_size=4096, max_size=16384, window_size=32)

    encode_file(
        in_path=src_a,
        genome_path=genome_a,
        out_seed_path=tmp_path / "a.hlx",
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )
    encode_file(
        in_path=src_b,
        genome_path=genome_b,
        out_seed_path=tmp_path / "b.hlx",
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    source = open_genome(genome_a)
    try:
        expected_count = source.count_chunks()
    finally:
        source.close()
    snapshot_genome(genome_a, snapshot)
    restore_genome(snapshot, genome_b, replace=True)

    restored = open_genome(genome_b)
    try:
        assert restored.count_chunks() == expected_count
    finally:
        restored.close()
