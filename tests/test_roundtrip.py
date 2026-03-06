from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import decode_file, encode_file, sha256_file


def test_roundtrip_bit_perfect(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    out = tmp_path / "decoded.bin"
    seed = tmp_path / "seed.hlx"
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
