from __future__ import annotations

from pathlib import Path

import pytest

from helix.chunking import ChunkerConfig
from helix.codec import decode_file, encode_file, verify_seed
from helix.errors import SeedFormatError


def test_encrypted_seed_roundtrip_requires_key(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    out = tmp_path / "decoded.bin"
    genome = tmp_path / "genome"

    src.write_bytes((b"encrypted-seed" * 4000) + bytes(range(128)))
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
        encryption_key="correct-key",
    )

    assert seed.read_bytes().startswith(b"HLE1")

    with pytest.raises(
        SeedFormatError, match="Encrypted seed requires decryption key"
    ):
        decode_file(seed, genome, out)

    with pytest.raises(SeedFormatError, match="authentication failed"):
        decode_file(seed, genome, out, encryption_key="wrong-key")

    decode_file(seed, genome, out, encryption_key="correct-key")
    assert out.read_bytes() == src.read_bytes()


def test_verify_strict_with_encrypted_seed(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    genome = tmp_path / "genome"

    src.write_bytes((b"verify-encrypted" * 2500) + b"tail")
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
        encryption_key="verify-key",
    )

    with pytest.raises(
        SeedFormatError, match="Encrypted seed requires decryption key"
    ):
        verify_seed(seed, genome, strict=True)

    report = verify_seed(
        seed, genome, strict=True, encryption_key="verify-key"
    )
    assert report.ok
