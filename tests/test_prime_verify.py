from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import encode_file, prime_genome, verify_seed


def test_prime_then_verify(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.bin").write_bytes((b"abcd" * 20_000) + b"X")
    (corpus / "b.bin").write_bytes((b"abcd" * 20_000) + b"Y")

    genome = tmp_path / "genome"
    cfg = ChunkerConfig(min_size=1024, avg_size=4096, max_size=16384, window_size=32)

    stats = prime_genome(corpus, genome, chunker="cdc_buzhash", cfg=cfg)
    assert stats["total_chunks"] > 0

    seed = tmp_path / "seed.hlx"
    encode_file(
        in_path=corpus / "a.bin",
        genome_path=genome,
        out_seed_path=seed,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    report = verify_seed(seed, genome, strict=True)
    assert report.ok
