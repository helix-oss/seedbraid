from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import decode_file, encode_file, export_genes, import_genes


def test_export_import_genes_pack_allows_decode_on_fresh_genome(
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    genes = tmp_path / "genes.pack"
    out = tmp_path / "decoded.bin"

    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src.write_bytes((b"chunk-A" * 20_000) + (b"chunk-B" * 20_000))
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

    exp = export_genes(seed, genome_a, genes)
    assert exp["exported"] > 0

    imp = import_genes(genes, genome_b)
    assert imp["inserted"] > 0

    decode_file(seed, genome_b, out)
    assert out.read_bytes() == src.read_bytes()
