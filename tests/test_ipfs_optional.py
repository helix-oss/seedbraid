from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from helix.chunking import ChunkerConfig
from helix.codec import encode_file
from helix.ipfs import fetch_seed, publish_seed


def test_publish_fetch_if_ipfs_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("ipfs") is None:
        pytest.skip("ipfs CLI not installed")

    ipfs_repo = tmp_path / "ipfs-repo"
    monkeypatch.setenv("IPFS_PATH", str(ipfs_repo))
    init = subprocess.run(
        ["ipfs", "init"], check=False, capture_output=True, text=True
    )
    if init.returncode != 0:
        pytest.skip(
            f"ipfs init failed in test environment: {init.stderr.strip()}"
        )

    src = tmp_path / "s.bin"
    seed = tmp_path / "s.hlx"
    fetched = tmp_path / "fetched.hlx"
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
