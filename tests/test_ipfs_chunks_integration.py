"""IPFS distributed chunks E2E integration tests.

Tests are skipped automatically when the kubo daemon
is not reachable via HTTP API.  Start a local daemon
with ``ipfs daemon`` before running these tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from seedbraid import ipfs_http
from seedbraid.chunk_manifest import (
    manifest_path_for_seed,
    read_chunk_manifest,
    write_chunk_manifest,
)
from seedbraid.chunking import ChunkerConfig
from seedbraid.cid import sha256_to_cidv1_raw
from seedbraid.codec import (
    EncodeStats,
    encode_file,
    sha256_file,
)
from seedbraid.ipfs_chunks import (
    fetch_decode_from_ipfs,
    publish_chunks_from_genome,
)
from seedbraid.storage import open_genome

_CFG = ChunkerConfig(
    min_size=1024,
    avg_size=1024,
    max_size=1024,
    window_size=16,
)
_CHUNKER = "fixed"
_RETRIES = 2
_BACKOFF_MS = 50


def _deterministic_data(size: int) -> bytes:
    """Generate deterministic pseudo-random bytes."""
    pattern = hashlib.sha256(
        size.to_bytes(8, "big"),
    ).digest()
    repeats = (size // len(pattern)) + 1
    return (pattern * repeats)[:size]


def _encode(
    src: Path,
    genome_path: Path,
    seed: Path,
) -> EncodeStats:
    """Encode with standard test parameters."""
    return encode_file(
        in_path=src,
        genome_path=genome_path,
        out_seed_path=seed,
        chunker=_CHUNKER,
        cfg=_CFG,
        learn=True,
        portable=False,
        manifest_compression="zlib",
    )


@pytest.fixture(scope="module")
def _require_kubo() -> None:
    """Skip module when kubo daemon is not reachable."""
    if not ipfs_http.check_daemon():
        pytest.skip("kubo daemon not reachable via HTTP API")


def test_publish_fetch_roundtrip_small(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """E2E: encode -> publish -> fetch-decode
    produces bit-perfect output."""
    src = tmp_path / "input.bin"
    data = _deterministic_data(10 * 1024)
    src.write_bytes(data)
    expected_sha = sha256_file(src)

    seed = tmp_path / "output.sbd"
    genome_path = tmp_path / "genome"
    _encode(src, genome_path, seed)

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
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
        retries=_RETRIES,
        backoff_ms=_BACKOFF_MS,
    )

    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_publish_fetch_roundtrip_with_dedup(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """Duplicate chunks are deduped on publish while
    roundtrip stays bit-perfect."""
    chunk = _deterministic_data(1024)
    data = chunk * 10
    src = tmp_path / "dup.bin"
    src.write_bytes(data)
    expected_sha = sha256_file(src)

    seed = tmp_path / "dup.sbd"
    genome_path = tmp_path / "genome-dup"
    stats = _encode(src, genome_path, seed)
    assert stats.total_chunks == 10
    assert stats.unique_hashes == 1

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
        )
    assert len(manifest.chunks) == 1

    decoded = tmp_path / "dup-decoded.bin"
    actual_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
        batch_size=100,
        retries=_RETRIES,
        backoff_ms=_BACKOFF_MS,
    )
    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_manifest_sidecar_roundtrip(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """Manifest written by publish matches when
    read back from disk."""
    src = tmp_path / "mf.bin"
    src.write_bytes(_deterministic_data(5 * 1024))

    seed = tmp_path / "mf.sbd"
    genome_path = tmp_path / "genome-mf"
    _encode(src, genome_path, seed)

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
        )
    assert len(manifest.chunks) > 0

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
    _require_kubo: None,
) -> None:
    """Returned SHA-256 from fetch_decode matches
    sha256_file on the reconstructed output."""
    src = tmp_path / "sha.bin"
    data = _deterministic_data(8 * 1024)
    src.write_bytes(data)

    seed = tmp_path / "sha.sbd"
    genome_path = tmp_path / "genome-sha"
    _encode(src, genome_path, seed)

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
        )
    assert len(manifest.chunks) > 0

    decoded = tmp_path / "sha-decoded.bin"
    returned_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=4,
        retries=_RETRIES,
        backoff_ms=_BACKOFF_MS,
    )
    assert returned_sha == sha256_file(decoded)
    assert returned_sha == sha256_file(src)


def test_e2e_with_batch_size_1(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """batch_size=1 forces every op into its own
    batch, exercising all boundary conditions."""
    src = tmp_path / "batch.bin"
    data = _deterministic_data(3 * 1024)
    src.write_bytes(data)
    expected_sha = sha256_file(src)

    seed = tmp_path / "batch.sbd"
    genome_path = tmp_path / "genome-batch"
    _encode(src, genome_path, seed)

    with open_genome(genome_path) as genome:
        manifest = publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
        )
    assert len(manifest.chunks) > 0

    decoded = tmp_path / "batch-decoded.bin"
    actual_sha = fetch_decode_from_ipfs(
        seed_path=seed,
        out_path=decoded,
        max_workers=1,
        batch_size=1,
        retries=_RETRIES,
        backoff_ms=_BACKOFF_MS,
    )
    assert actual_sha == expected_sha
    assert decoded.read_bytes() == data


def test_progress_callback_invoked(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """Progress callbacks fire for both publish
    and fetch-decode phases."""
    src = tmp_path / "prog.bin"
    src.write_bytes(_deterministic_data(3 * 1024))

    seed = tmp_path / "prog.sbd"
    genome_path = tmp_path / "genome-prog"
    _encode(src, genome_path, seed)

    pub_calls: list[tuple[int, int]] = []
    with open_genome(genome_path) as genome:
        publish_chunks_from_genome(
            seed_path=seed,
            genome=genome,
            max_workers=4,
            retries=_RETRIES,
            backoff_ms=_BACKOFF_MS,
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
        retries=_RETRIES,
        backoff_ms=_BACKOFF_MS,
        progress_callback=lambda d, t: (
            fetch_calls.append((d, t))
        ),
    )
    assert len(fetch_calls) > 0
    assert fetch_calls[-1][0] == fetch_calls[-1][1]


def test_cid_matches_ipfs_block_put(
    tmp_path: Path,
    _require_kubo: None,
) -> None:
    """Python-computed CID matches kubo HTTP API
    block put output for raw codec blocks."""
    data = b"cid verification test payload"
    expected_cid = sha256_to_cidv1_raw(data)

    result = ipfs_http.post_multipart_json(
        "/block/put",
        "data",
        data,
        **{"cid-codec": "raw", "mhtype": "sha2-256"},
    )
    actual_cid = result.get("Key", "")
    assert actual_cid == expected_cid
