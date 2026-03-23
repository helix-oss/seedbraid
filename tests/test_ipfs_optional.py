from __future__ import annotations

from pathlib import Path

import pytest

from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import encode_file
from seedbraid.ipfs import fetch_seed, publish_seed


def test_publish_fetch_if_ipfs_installed(
    tmp_path: Path,
) -> None:
    from seedbraid.ipfs_http import check_daemon

    if not check_daemon():
        pytest.skip("kubo daemon not reachable via HTTP API")

    src = tmp_path / "s.bin"
    seed = tmp_path / "s.sbd"
    fetched = tmp_path / "fetched.sbd"
    genome = tmp_path / "genome"
    src.write_bytes(b"hello ipfs" * 1000)

    encode_file(
        in_path=src,
        genome_path=genome,
        out_seed_path=seed,
        chunker="fixed",
        cfg=ChunkerConfig(
            min_size=1024, avg_size=1024, max_size=1024, window_size=16
        ),
        learn=True,
        portable=True,
        manifest_compression="zlib",
    )

    cid = publish_seed(seed, pin=False)
    assert cid

    fetch_seed(cid, fetched)
    assert fetched.exists()
    assert fetched.read_bytes() == seed.read_bytes()
