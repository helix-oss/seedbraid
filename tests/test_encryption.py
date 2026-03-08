from __future__ import annotations

import struct
from pathlib import Path

import pytest

from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import decode_file, encode_file, verify_seed
from seedbraid.errors import SeedFormatError


def test_encrypted_seed_roundtrip_requires_key(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
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

    assert seed.read_bytes().startswith(b"SBE1")

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
    seed = tmp_path / "seed.sbd"
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


def test_encrypted_v3_roundtrip(tmp_path: Path) -> None:
    """New encryptions use v3 AEAD format with n=32768."""
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.sbd"
    out = tmp_path / "decoded.bin"
    genome = tmp_path / "genome"

    src.write_bytes(b"v3-test-data" * 3000)
    cfg = ChunkerConfig(
        min_size=1024,
        avg_size=4096,
        max_size=16384,
        window_size=32,
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
        encryption_key="v3key",
    )

    blob = seed.read_bytes()
    assert blob[:4] == b"SBE1"
    version = struct.unpack_from(">H", blob, 4)[0]
    assert version == 3
    scrypt_n = struct.unpack_from(">I", blob, 20)[0]
    assert scrypt_n == 32768

    decode_file(seed, genome, out, encryption_key="v3key")
    assert out.read_bytes() == src.read_bytes()
