from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import encode_file, verify_seed
from helix.container import read_seed, write_seed


def test_verify_strict_detects_manifest_hash_mismatch(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    genome = tmp_path / "genome"
    seed = tmp_path / "seed.hlx"
    tampered = tmp_path / "tampered.hlx"

    src.write_bytes((b"strict-mode" * 5000) + b"!" * 128)
    cfg = ChunkerConfig(min_size=1024, avg_size=4096, max_size=16384, window_size=32)

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

    parsed = read_seed(seed)
    manifest = dict(parsed.manifest)
    manifest["source_sha256"] = "0" * 64

    write_seed(
        tampered,
        manifest,
        parsed.recipe,
        parsed.raw_payloads,
        parsed.manifest_compression,
    )

    quick_report = verify_seed(tampered, genome, strict=False)
    assert quick_report.ok
    assert quick_report.actual_sha256 is None

    strict_report = verify_seed(tampered, genome, strict=True)
    assert not strict_report.ok
    assert strict_report.reason == "Reconstructed SHA-256 mismatch."
    assert strict_report.actual_sha256 is not None
