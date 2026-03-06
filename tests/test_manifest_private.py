from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import encode_file, verify_seed
from helix.container import read_seed


def test_manifest_private_minimizes_metadata_and_preserves_verify(
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    genome = tmp_path / "genome"
    src.write_bytes((b"manifest-private" * 3000) + bytes(range(64)))

    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=seed,
        chunker="fixed",
        cfg=ChunkerConfig(
            min_size=1024, avg_size=1024, max_size=1024, window_size=16
        ),
        learn=True,
        portable=False,
        manifest_compression="zlib",
        manifest_private=True,
    )

    parsed = read_seed(seed)
    manifest = parsed.manifest
    assert manifest["manifest_private"] is True
    assert manifest["source_size"] is None
    assert manifest["source_sha256"] is None
    assert manifest["chunker"] == {"name": "fixed"}
    assert "created_at" not in manifest
    assert "stats" not in manifest

    report = verify_seed(seed, genome, strict=True)
    assert report.ok
    assert report.expected_sha256 is None
    assert report.actual_sha256 is not None
