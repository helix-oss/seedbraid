from __future__ import annotations

from pathlib import Path

import pytest

from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import (
    decode_file,
    encode_file,
    export_genes,
    import_genes,
)
from seedbraid.errors import ACTION_VERIFY_GENES_PACK, SeedbraidError


def test_export_import_genes_pack_allows_decode_on_fresh_genome(
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
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


def test_import_genes_bad_magic_has_next_action(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "bad.pack"
    pack.write_bytes(b"BADMAGIC")
    with pytest.raises(SeedbraidError) as exc_info:
        import_genes(pack, tmp_path / "genome")
    assert (
        exc_info.value.next_action
        == ACTION_VERIFY_GENES_PACK
    )


def test_import_genes_rejects_corrupted_pack(
    tmp_path: Path,
) -> None:
    """Corrupted genes payload triggers hash mismatch."""
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
    genes = tmp_path / "genes.pack"
    genome_a = tmp_path / "genome-a"
    genome_b = tmp_path / "genome-b"

    src.write_bytes(
        (b"genes-corrupt-" * 20_000)
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
    export_genes(seed, genome_a, genes)

    # Corrupt a payload in the genes pack binary
    raw = bytearray(genes.read_bytes())
    # Header = GENE1(5) + count(4) = 9
    # First entry = hash(32) + size(4) + payload(size)
    # Corrupt the first byte of the payload
    payload_offset = 9 + 32 + 4
    raw[payload_offset] ^= 0xFF
    genes.write_bytes(bytes(raw))

    with pytest.raises(
        SeedbraidError, match="hash mismatch",
    ):
        import_genes(genes, genome_b)


def test_import_genes_truncated_hash_has_next_action(
    tmp_path: Path,
) -> None:
    pack = tmp_path / "trunc.pack"
    pack.write_bytes(b"GENE1" + (1).to_bytes(4, "big") + b"\x00" * 10)
    with pytest.raises(SeedbraidError) as exc_info:
        import_genes(pack, tmp_path / "genome")
    assert (
        exc_info.value.next_action
        == ACTION_VERIFY_GENES_PACK
    )
