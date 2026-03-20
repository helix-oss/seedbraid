"""IPFS distributed chunks E2E integration tests.

Tests are skipped automatically when the ``ipfs``
CLI is not installed or cannot be initialized.
Requires a local Kubo node (daemon not needed --
``ipfs block put/get`` operates on the local
blockstore directly).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from seedbraid.chunk_manifest import (
    manifest_path_for_seed,
    read_chunk_manifest,
    write_chunk_manifest,
)
from seedbraid.chunking import ChunkerConfig
from seedbraid.codec import encode_file, sha256_file
from seedbraid.ipfs_chunks import (
    fetch_decode_from_ipfs,
    publish_chunks_from_genome,
)
from seedbraid.storage import open_genome

# Fixed chunk size for deterministic tests
_CFG = ChunkerConfig(
    min_size=1024,
    avg_size=1024,
    max_size=1024,
    window_size=16,
)
_CHUNKER = "fixed"


def _deterministic_data(size: int) -> bytes:
    """Generate deterministic pseudo-random bytes."""
    pattern = hashlib.sha256(
        size.to_bytes(8, "big"),
    ).digest()
    repeats = (size // len(pattern)) + 1
    return (pattern * repeats)[:size]


@pytest.fixture(scope="module")
def ipfs_repo(tmp_path_factory):
    """Initialize an isolated IPFS repo.

    Skips the entire module when ``ipfs`` CLI is
    not installed or ``ipfs init`` fails.
    """
    if shutil.which("ipfs") is None:
        pytest.skip("ipfs CLI not installed")
    repo = tmp_path_factory.mktemp("ipfs-repo")
    result = subprocess.run(
        ["ipfs", "init"],
        env={**os.environ, "IPFS_PATH": str(repo)},
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            "ipfs init failed:"
            f" {result.stderr.strip()}"
        )
    return repo


def test_publish_fetch_roundtrip_small(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E: encode -> publish -> fetch-decode
    produces bit-perfect output."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    src = tmp_path / "input.bin"
    data = _deterministic_data(10 * 1024)
    src.write_bytes(data)
    expected_sha = hashlib.sha256(data).hexdigest()

    seed = tmp_path / "output.sbd"
    genome_path = tmp_path / "genome"
    encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=2,
            backoff_ms=50,
        )
    assert len(manifest.chunks) > 0

    manifest_file = manifest_path_for_seed(seed)
    write_chunk_manifest(manifest, manifest_file)
    assert manifest_file.exists()

    decoded = tmp_path / "decoded.bin"
    actual_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
        batch_size=100,
        retries=2,
        backoff_ms=50,
    )

    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_publish_fetch_roundtrip_with_dedup(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate chunks are deduped on publish while
    roundtrip stays bit-perfect."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    chunk = _deterministic_data(1024)
    data = chunk * 10
    src = tmp_path / "dup.bin"
    src.write_bytes(data)
    expected_sha = hashlib.sha256(data).hexdigest()

    seed = tmp_path / "dup.sbd"
    genome_path = tmp_path / "genome-dup"
    stats = encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )
    assert stats.total_chunks == 10
    assert stats.unique_hashes == 1

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
        )
    assert len(manifest.chunks) == 1

    decoded = tmp_path / "dup-decoded.bin"
    actual_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
        batch_size=100,
    )
    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_manifest_sidecar_roundtrip(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest written by publish matches when
    read back from disk."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    src = tmp_path / "mf.bin"
    src.write_bytes(_deterministic_data(5 * 1024))

    seed = tmp_path / "mf.sbd"
    genome_path = tmp_path / "genome-mf"
    encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
        )

    mf_path = manifest_path_for_seed(seed)
    write_chunk_manifest(manifest, mf_path)

    loaded = read_chunk_manifest(mf_path)
    assert loaded.seed_sha256 == manifest.seed_sha256
    assert len(loaded.chunks) == len(manifest.chunks)
    for orig, read in zip(
        manifest.chunks, loaded.chunks, strict=True,
    ):
        assert orig.hash_hex == read.hash_hex
        assert orig.cid == read.cid


def test_fetch_decode_sha256_verification(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returned SHA-256 from fetch_decode matches
    sha256_file on the reconstructed output."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    src = tmp_path / "sha.bin"
    data = _deterministic_data(8 * 1024)
    src.write_bytes(data)

    seed = tmp_path / "sha.sbd"
    genome_path = tmp_path / "genome-sha"
    encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    with open_genome(genome_path) as genome:
        publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
        )

    decoded = tmp_path / "sha-decoded.bin"
    returned_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
    )
    assert returned_sha == sha256_file(decoded)
    assert returned_sha == sha256_file(src)


def test_e2e_with_batch_size_1(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """batch_size=1 forces every op into its own
    batch, exercising all boundary conditions."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    src = tmp_path / "batch.bin"
    data = _deterministic_data(3 * 1024)
    src.write_bytes(data)
    expected_sha = hashlib.sha256(data).hexdigest()

    seed = tmp_path / "batch.sbd"
    genome_path = tmp_path / "genome-batch"
    encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    with open_genome(genome_path) as genome:
        publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
        )

    decoded = tmp_path / "batch-decoded.bin"
    actual_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=1,
        batch_size=1,
    )
    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_progress_callback_invoked(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progress callbacks fire for both publish
    and fetch-decode phases."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )

    src = tmp_path / "prog.bin"
    src.write_bytes(_deterministic_data(3 * 1024))

    seed = tmp_path / "prog.sbd"
    genome_path = tmp_path / "genome-prog"
    encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )

    pub_calls: list[tuple[int, int]] = []
    with open_genome(genome_path) as genome:
        publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            progress_callback=lambda d, t: (
                pub_calls.append((d, t))
            ),
        )
    assert len(pub_calls) > 0
    assert pub_calls[-1][0] == pub_calls[-1][1]

    fetch_calls: list[tuple[int, int]] = []
    decoded = tmp_path / "prog-decoded.bin"
    fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
        progress_callback=lambda d, t: (
            fetch_calls.append((d, t))
        ),
    )
    assert len(fetch_calls) > 0
    assert fetch_calls[-1][0] == fetch_calls[-1][1]


def test_cid_matches_ipfs_block_put(
    tmp_path: Path,
    ipfs_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python-computed CID matches ipfs block put
    output for raw codec blocks."""
    monkeypatch.setenv(
        "IPFS_PATH", str(ipfs_repo),
    )
    from seedbraid.cid import sha256_to_cidv1_raw

    data = b"cid verification test payload"
    expected_cid = sha256_to_cidv1_raw(data)

    proc = subprocess.run(
        [
            "ipfs", "block", "put",
            "--cid-codec", "raw",
        ],
        input=data,
        check=True,
        capture_output=True,
    )
    actual_cid = proc.stdout.decode().strip()
    assert actual_cid == expected_cid
