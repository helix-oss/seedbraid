from __future__ import annotations

from pathlib import Path

from helix.chunking import ChunkerConfig
from helix.codec import encode_file, verify_seed
from helix.container import parse_seed, sign_seed_file


def test_sign_and_verify_with_required_signature(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    unsigned = tmp_path / "seed.hlx"
    signed = tmp_path / "seed.signed.hlx"
    genome = tmp_path / "genome"

    src.write_bytes((b"signed-seed" * 5000) + b"!" * 64)
    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=unsigned,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    sign_seed_file(
        unsigned, signed, signature_key="top-secret", signature_key_id="team-a"
    )

    seed = parse_seed(signed.read_bytes())
    assert seed.signature is not None
    assert seed.signature["algorithm"] == "hmac-sha256"

    report = verify_seed(
        signed,
        genome,
        strict=True,
        require_signature=True,
        signature_key="top-secret",
    )
    assert report.ok


def test_verify_fails_on_missing_or_invalid_signature(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    unsigned = tmp_path / "seed.hlx"
    signed = tmp_path / "seed.signed.hlx"
    genome = tmp_path / "genome"

    src.write_bytes((b"signed-seed" * 2000) + b"@" * 10)
    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=unsigned,
        chunker="cdc_buzhash",
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    missing = verify_seed(
        unsigned, genome, strict=False, require_signature=True
    )
    assert not missing.ok
    assert missing.reason == "Signature is required but missing."

    sign_seed_file(unsigned, signed, signature_key="correct-key")
    invalid = verify_seed(
        signed,
        genome,
        strict=False,
        require_signature=True,
        signature_key="wrong-key",
    )
    assert not invalid.ok
    assert invalid.reason == "Signature verification failed."
