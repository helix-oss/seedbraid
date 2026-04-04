"""Unit tests for IPFSChunkStorage (monkeypatch, no IPFS daemon)."""

from __future__ import annotations

import hashlib

import pytest
from typer.testing import CliRunner

from seedbraid.chunk_manifest import ChunkEntry, ChunkManifest
from seedbraid.cid import sha256_to_cidv1_raw
from seedbraid.cli import app
from seedbraid.container import OP_REF, Recipe, RecipeOp, Seed
from seedbraid.errors import DecodeError, ExternalToolError
from seedbraid.ipfs_chunks import (
    IPFSChunkStorage,
    create_chunk_dag,
    fetch_chunk,
    fetch_chunks_parallel,
    fetch_decode_from_ipfs,
    publish_chunk,
    publish_chunks_from_genome,
)

_cli_runner = CliRunner()


_CHUNK_DATA = b"hello ipfs chunk"
_CHUNK_HASH = hashlib.sha256(_CHUNK_DATA).digest()
_CHUNK_CID = sha256_to_cidv1_raw(_CHUNK_DATA)


# -- has_chunk -----------------------------------------------


def test_has_chunk_returns_true_on_stat_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        lambda path, **params: {
            "Key": params.get("arg", ""),
            "Size": 16,
        },
    )
    storage = IPFSChunkStorage()
    assert storage.has_chunk(_CHUNK_HASH) is True


def test_has_chunk_returns_false_on_stat_failure(
    monkeypatch,
) -> None:
    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "block not found",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fail,
    )
    storage = IPFSChunkStorage()
    assert storage.has_chunk(_CHUNK_HASH) is False


# -- get_chunk -----------------------------------------------


def test_get_chunk_returns_data_on_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        lambda path, **params: _CHUNK_DATA,
    )
    storage = IPFSChunkStorage()
    result = storage.get_chunk(_CHUNK_HASH)
    assert result == _CHUNK_DATA


def test_get_chunk_returns_none_on_failure(
    monkeypatch,
) -> None:
    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "offline",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )
    storage = IPFSChunkStorage(retries=2)
    assert storage.get_chunk(_CHUNK_HASH) is None


def test_get_chunk_retries_with_backoff(
    monkeypatch,
) -> None:
    calls = [0]
    sleeps: list[float] = []

    def _fake_post_raw(path, **params):  # noqa: ANN001, ANN003, ANN202
        calls[0] += 1
        if calls[0] < 3:
            raise ExternalToolError(
                "timeout",
                code="SB_E_KUBO_API_ERROR",
            )
        return _CHUNK_DATA

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fake_post_raw,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda s: sleeps.append(s),
    )

    storage = IPFSChunkStorage(
        retries=3, backoff_ms=100,
    )
    result = storage.get_chunk(_CHUNK_HASH)
    assert result == _CHUNK_DATA
    assert len(sleeps) == 2
    assert sleeps[0] == pytest.approx(0.1)
    assert sleeps[1] == pytest.approx(0.2)


def test_get_chunk_gateway_fallback(
    monkeypatch,
) -> None:
    urls: list[str] = []

    class _Resp:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, *a):  # noqa: ANN001, ANN201
            return False

        def read(self) -> bytes:
            return self._data

    def _fake_urlopen(url, timeout=30):  # noqa: ANN001, ANN202
        urls.append(url)
        return _Resp(_CHUNK_DATA)

    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "offline",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.urllib.request.urlopen",
        _fake_urlopen,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )

    storage = IPFSChunkStorage(
        gateway="https://gw.example/ipfs",
        retries=1,
    )
    result = storage.get_chunk(_CHUNK_HASH)
    assert result == _CHUNK_DATA
    expected_url = (
        f"https://gw.example/ipfs/{_CHUNK_CID}"
    )
    assert urls == [expected_url]


def test_get_chunk_rejects_mismatched_hash(
    monkeypatch,
) -> None:
    """kubo API returns wrong data → CID mismatch."""
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        lambda path, **params: b"corrupted",
    )
    storage = IPFSChunkStorage()
    with pytest.raises(
        ExternalToolError, match="hash mismatch",
    ) as exc_info:
        storage.get_chunk(_CHUNK_HASH)
    assert (
        exc_info.value.code
        == "SB_E_IPFS_CID_MISMATCH"
    )


def test_get_chunk_gateway_rejects_mismatched_hash(
    monkeypatch,
) -> None:
    """Gateway returns wrong data → CID mismatch."""

    class _Resp:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, *a):  # noqa: ANN001, ANN201
            return False

        def read(self) -> bytes:
            return b"tampered"

    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "offline",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw", _fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.urllib.request.urlopen",
        lambda url, timeout=30: _Resp(),
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )

    storage = IPFSChunkStorage(
        gateway="https://gw.example/ipfs",
        retries=1,
    )
    with pytest.raises(
        ExternalToolError, match="hash mismatch",
    ):
        storage.get_chunk(_CHUNK_HASH)


# -- put_chunk -----------------------------------------------


def test_put_chunk_success_with_cid_verification(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        lambda path, field, data, **params: {
            "Key": _CHUNK_CID,
        },
    )
    storage = IPFSChunkStorage()
    result = storage.put_chunk(
        _CHUNK_HASH, _CHUNK_DATA,
    )
    assert result is True
    assert storage.count_chunks() == 1


def test_put_chunk_cid_mismatch_raises(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        lambda path, field, data, **params: {
            "Key": "bafkreiwrong",
        },
    )
    storage = IPFSChunkStorage()
    with pytest.raises(
        ExternalToolError,
        match="CID mismatch",
    ) as exc_info:
        storage.put_chunk(_CHUNK_HASH, _CHUNK_DATA)
    assert exc_info.value.code == (
        "SB_E_IPFS_CID_MISMATCH"
    )


def test_put_chunk_retries_on_failure(
    monkeypatch,
) -> None:
    calls = [0]

    def _fake_put(path, field, data, **params):  # noqa: ANN001, ANN003, ANN202
        calls[0] += 1
        if calls[0] == 1:
            raise ExternalToolError(
                "daemon offline",
                code="SB_E_KUBO_API_ERROR",
            )
        return {"Key": _CHUNK_CID}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        _fake_put,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )

    storage = IPFSChunkStorage(retries=2)
    assert storage.put_chunk(
        _CHUNK_HASH, _CHUNK_DATA,
    ) is True
    assert calls[0] == 2


def test_put_chunk_all_retries_exhausted_raises(
    monkeypatch,
) -> None:
    def _always_fail(path, field, data, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "daemon offline",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        _always_fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )

    storage = IPFSChunkStorage(retries=2)
    with pytest.raises(
        ExternalToolError,
        match="Failed to publish chunk",
    ) as exc_info:
        storage.put_chunk(_CHUNK_HASH, _CHUNK_DATA)
    assert exc_info.value.code == (
        "SB_E_IPFS_CHUNK_PUT"
    )


# -- context manager / count ---------------------------------


def test_context_manager(monkeypatch) -> None:
    with IPFSChunkStorage() as storage:
        assert storage is not None


def test_count_chunks_increments(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        lambda path, field, data, **params: {
            "Key": _CHUNK_CID,
        },
    )
    storage = IPFSChunkStorage()
    assert storage.count_chunks() == 0
    storage.put_chunk(_CHUNK_HASH, _CHUNK_DATA)
    assert storage.count_chunks() == 1
    storage.put_chunk(_CHUNK_HASH, _CHUNK_DATA)
    assert storage.count_chunks() == 2


# -- standalone functions ------------------------------------


def test_publish_chunk_standalone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        lambda path, field, data, **params: {
            "Key": _CHUNK_CID,
        },
    )
    cid = publish_chunk(_CHUNK_DATA)
    assert cid == _CHUNK_CID


def test_fetch_chunk_standalone_raises_on_unavailable(
    monkeypatch,
) -> None:
    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "not found",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )
    with pytest.raises(
        ExternalToolError,
        match="not available",
    ) as exc_info:
        fetch_chunk(_CHUNK_CID)
    assert exc_info.value.code == (
        "SB_E_IPFS_CHUNK_GET"
    )


# -- error: kubo API unreachable ----------------------------


def test_kubo_api_unreachable_returns_false(
    monkeypatch,
) -> None:
    """has_chunk returns False when kubo API is unreachable."""
    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "Cannot reach kubo API",
            code="SB_E_KUBO_API_UNREACHABLE",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fail,
    )
    storage = IPFSChunkStorage()
    assert storage.has_chunk(_CHUNK_HASH) is False


# -- publish_chunks_from_genome helpers ----------------------


def _make_chunk_entry(
    digest: bytes,
) -> ChunkEntry:
    """Create a ChunkEntry from digest."""
    return ChunkEntry(
        hash_hex=digest.hex(),
        cid=sha256_to_cidv1_raw(
            digest, is_digest=True,
        ),
    )


def _raise_external(**kw):  # noqa: ANN003, ANN202
    raise ExternalToolError(
        "test error",
        code="SB_E_IPFS_CHUNK_PUT",
        next_action="check ipfs",
    )


def _make_seed(digests: list[bytes]) -> Seed:
    """Build a minimal Seed for testing."""
    return Seed(
        manifest={"format": "SBD1", "version": 1},
        recipe=Recipe(
            hash_table=digests,
            ops=[
                RecipeOp(opcode=OP_REF, hash_index=i)
                for i in range(len(digests))
            ],
        ),
        raw_payloads={},
        manifest_compression="none",
        signature=None,
        signed_payload=None,
    )


class _MockGenome:
    """GenomeStorage mock backed by a dict."""

    def __init__(
        self, chunks: dict[bytes, bytes],
    ) -> None:
        self._chunks = chunks

    def get_chunk(
        self, chunk_hash: bytes,
    ) -> bytes | None:
        return self._chunks.get(chunk_hash)

    def has_chunk(
        self, chunk_hash: bytes,
    ) -> bool:
        return chunk_hash in self._chunks

    def put_chunk(
        self, chunk_hash: bytes, data: bytes,
    ) -> bool:
        self._chunks[chunk_hash] = data
        return True

    def count_chunks(self) -> int:
        return len(self._chunks)

    def close(self) -> None:
        pass

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *a):  # noqa: ANN002, ANN204
        pass


_SEED_SHA = "aa" * 32
_CHUNK_A = b"chunk-alpha"
_CHUNK_B = b"chunk-bravo"
_DIGEST_A = hashlib.sha256(_CHUNK_A).digest()
_DIGEST_B = hashlib.sha256(_CHUNK_B).digest()


def _patch_publish_deps(
    monkeypatch,
    digests: list[bytes],
):  # noqa: ANN001, ANN202
    """Patch read_seed, sha256_file, ipfs_http, time."""
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.read_seed",
        lambda path, **kw: _make_seed(digests),
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.sha256_file",
        lambda path: _SEED_SHA,
    )

    def _fake_put(path, field, data, **params):  # noqa: ANN001, ANN003, ANN202
        cid = sha256_to_cidv1_raw(data)
        return {"Key": cid}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        _fake_put,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )


# -- publish_chunks_from_genome tests ------------------------


def test_publish_chunks_from_genome_basic(
    monkeypatch, tmp_path,
) -> None:
    """All unique chunks are published."""
    genome = _MockGenome(
        {_DIGEST_A: _CHUNK_A, _DIGEST_B: _CHUNK_B},
    )
    _patch_publish_deps(
        monkeypatch,
        [_DIGEST_A, _DIGEST_B],
    )

    manifest = publish_chunks_from_genome(
        seed_path=tmp_path / "test.sbd",
        genome=genome,
        max_workers=1,
    )
    assert isinstance(manifest, ChunkManifest)
    assert len(manifest.chunks) == 2
    assert manifest.chunks[0].hash_hex == (
        _DIGEST_A.hex()
    )
    assert manifest.chunks[1].hash_hex == (
        _DIGEST_B.hex()
    )


def test_publish_chunks_from_genome_dedup(
    monkeypatch, tmp_path,
) -> None:
    """Duplicate digests are published only once."""
    put_calls: list[bytes] = []

    genome = _MockGenome({_DIGEST_A: _CHUNK_A})
    _patch_publish_deps(
        monkeypatch,
        [_DIGEST_A, _DIGEST_A, _DIGEST_A],
    )

    def _tracking_put(path, field, data, **params):  # noqa: ANN001, ANN003, ANN202
        put_calls.append(data)
        cid = sha256_to_cidv1_raw(data)
        return {"Key": cid}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        _tracking_put,
    )

    manifest = publish_chunks_from_genome(
        seed_path=tmp_path / "test.sbd",
        genome=genome,
        max_workers=1,
    )
    assert len(manifest.chunks) == 1
    assert len(put_calls) == 1


def test_publish_chunks_progress_callback(
    monkeypatch, tmp_path,
) -> None:
    """Progress callback is called with correct args."""
    genome = _MockGenome(
        {_DIGEST_A: _CHUNK_A, _DIGEST_B: _CHUNK_B},
    )
    _patch_publish_deps(
        monkeypatch,
        [_DIGEST_A, _DIGEST_B],
    )

    progress: list[tuple[int, int]] = []
    manifest = publish_chunks_from_genome(
        seed_path=tmp_path / "test.sbd",
        genome=genome,
        max_workers=1,
        progress_callback=lambda d, t: (
            progress.append((d, t))
        ),
    )
    assert len(progress) == 2
    assert progress[-1] == (2, 2)
    assert manifest.seed_sha256 == _SEED_SHA


def test_publish_chunks_missing_chunk_raises(
    monkeypatch, tmp_path,
) -> None:
    """DecodeError when chunk is missing from genome."""
    genome = _MockGenome({})
    _patch_publish_deps(
        monkeypatch, [_DIGEST_A],
    )

    with pytest.raises(
        DecodeError, match="missing from genome",
    ):
        publish_chunks_from_genome(
            seed_path=tmp_path / "test.sbd",
            genome=genome,
        )


def test_publish_chunks_returns_manifest(
    monkeypatch, tmp_path,
) -> None:
    """Returned manifest has correct structure."""
    genome = _MockGenome({_DIGEST_A: _CHUNK_A})
    _patch_publish_deps(
        monkeypatch, [_DIGEST_A],
    )

    manifest = publish_chunks_from_genome(
        seed_path=tmp_path / "test.sbd",
        genome=genome,
        max_workers=1,
    )
    assert manifest.format == "SBD1-CHUNKS"
    assert manifest.version == 1
    assert manifest.seed_sha256 == _SEED_SHA
    assert manifest.dag_root_cid is None
    cid = sha256_to_cidv1_raw(
        _DIGEST_A, is_digest=True,
    )
    assert manifest.chunks[0].cid == cid


def test_publish_chunks_ipfs_error_propagates(
    monkeypatch, tmp_path,
) -> None:
    """ExternalToolError from put_chunk propagates."""
    genome = _MockGenome({_DIGEST_A: _CHUNK_A})
    _patch_publish_deps(
        monkeypatch, [_DIGEST_A],
    )

    def _always_fail(path, field, data, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "daemon offline",
            code="SB_E_IPFS_CHUNK_PUT",
            next_action="check ipfs",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_multipart_json",
        _always_fail,
    )

    with pytest.raises(
        ExternalToolError,
        match="Failed to publish chunk",
    ):
        publish_chunks_from_genome(
            seed_path=tmp_path / "test.sbd",
            genome=genome,
            max_workers=1,
        )


# -- publish-chunks CLI tests --------------------------------


def test_publish_chunks_cli_basic(
    monkeypatch, tmp_path,
) -> None:
    """CLI publish-chunks succeeds and writes manifest."""
    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )

    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        lambda **kw: manifest,
    )
    monkeypatch.setattr(
        "seedbraid.cli.write_chunk_manifest",
        lambda m, p: None,
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(tmp_path / "test.sbd"),
            "--genome",
            str(tmp_path / "g"),
        ],
    )
    assert result.exit_code == 0
    assert "published 1 chunks" in result.output


def test_publish_chunks_cli_manifest_path(
    monkeypatch, tmp_path,
) -> None:
    """--manifest-out writes to specified path."""
    custom_path = tmp_path / "custom.json"

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(_make_chunk_entry(_DIGEST_A),),
    )

    written: list[object] = []
    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        lambda **kw: manifest,
    )
    monkeypatch.setattr(
        "seedbraid.cli.write_chunk_manifest",
        lambda m, p: written.append(str(p)),
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(tmp_path / "test.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--manifest-out",
            str(custom_path),
        ],
    )
    assert result.exit_code == 0
    assert str(custom_path) in written


def test_publish_chunks_cli_default_manifest_path(
    monkeypatch, tmp_path,
) -> None:
    """Default manifest path is <seed>.sbd.chunks.json."""
    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(_make_chunk_entry(_DIGEST_A),),
    )

    written: list[object] = []
    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        lambda **kw: manifest,
    )
    monkeypatch.setattr(
        "seedbraid.cli.write_chunk_manifest",
        lambda m, p: written.append(str(p)),
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    seed = tmp_path / "data.sbd"
    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(seed),
            "--genome",
            str(tmp_path / "g"),
        ],
    )
    assert result.exit_code == 0
    assert str(seed) + ".chunks.json" in written


def test_publish_chunks_cli_error_handling(
    monkeypatch, tmp_path,
) -> None:
    """CLI exits with code 1 on error."""
    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        _raise_external,
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(tmp_path / "test.sbd"),
            "--genome",
            str(tmp_path / "g"),
        ],
    )
    assert result.exit_code == 1
    assert "SB_E_IPFS_CHUNK_PUT" in result.output


# -- fetch_chunks_parallel tests ----------------------------


def _patch_fetch_deps(
    monkeypatch,
    chunks: dict[bytes, bytes],
):  # noqa: ANN001, ANN202
    """Patch deps for parallel fetch tests."""
    cid_to_data: dict[str, bytes] = {}
    for digest, data in chunks.items():
        cid = sha256_to_cidv1_raw(
            digest, is_digest=True,
        )
        cid_to_data[cid] = data

    def _fake_post_raw(path, **params):  # noqa: ANN001, ANN003, ANN202
        cid = params.get("arg", "")
        if cid in cid_to_data:
            return cid_to_data[cid]
        raise ExternalToolError(
            "not found",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fake_post_raw,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )


def test_fetch_chunks_parallel_basic(
    monkeypatch,
) -> None:
    """Parallel fetch returns correct chunk data."""
    chunks = {
        _DIGEST_A: _CHUNK_A,
        _DIGEST_B: _CHUNK_B,
    }
    _patch_fetch_deps(monkeypatch, chunks)

    result = fetch_chunks_parallel(
        [_DIGEST_A, _DIGEST_B],
        max_workers=2,
    )
    assert result[_DIGEST_A] == _CHUNK_A
    assert result[_DIGEST_B] == _CHUNK_B


def test_fetch_chunks_parallel_dedup(
    monkeypatch,
) -> None:
    """Duplicate digests are fetched only once."""
    chunks = {_DIGEST_A: _CHUNK_A}
    _patch_fetch_deps(monkeypatch, chunks)

    calls: list[str] = []

    def _tracking_raw(path, **params):  # noqa: ANN001, ANN003, ANN202
        cid = params.get("arg", "")
        calls.append(cid)
        return _CHUNK_A

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _tracking_raw,
    )

    result = fetch_chunks_parallel(
        [_DIGEST_A, _DIGEST_A, _DIGEST_A],
        max_workers=1,
    )
    assert len(result) == 1
    assert result[_DIGEST_A] == _CHUNK_A
    assert len(calls) == 1


# -- fetch_decode_from_ipfs tests ---------------------------


def _patch_decode_deps(
    monkeypatch,
    chunks: dict[bytes, bytes],
    *,
    manifest_sha256: str | None = None,
):  # noqa: ANN001, ANN202
    """Patch deps for fetch_decode_from_ipfs tests."""
    _patch_fetch_deps(monkeypatch, chunks)

    digests = list(chunks.keys())
    expected_content = b"".join(
        chunks[d] for d in digests
    )
    source_sha = hashlib.sha256(
        expected_content,
    ).hexdigest()

    seed = _make_seed(digests)
    seed.manifest["source_sha256"] = (
        manifest_sha256
        if manifest_sha256 is not None
        else source_sha
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.read_seed",
        lambda path, **kw: seed,
    )


def test_fetch_decode_basic(
    monkeypatch, tmp_path,
) -> None:
    """Basic decode: 2 chunks fetched and joined."""
    chunks = {
        _DIGEST_A: _CHUNK_A,
        _DIGEST_B: _CHUNK_B,
    }
    _patch_decode_deps(monkeypatch, chunks)

    out = tmp_path / "output.bin"
    digest = fetch_decode_from_ipfs(
        seed_path=tmp_path / "test.sbd",
        out_path=out,
        max_workers=1,
        batch_size=100,
    )

    expected = _CHUNK_A + _CHUNK_B
    assert out.read_bytes() == expected
    assert digest == hashlib.sha256(
        expected,
    ).hexdigest()


def test_fetch_decode_batch_boundary(
    monkeypatch, tmp_path,
) -> None:
    """batch_size=1 processes each op separately."""
    chunks = {
        _DIGEST_A: _CHUNK_A,
        _DIGEST_B: _CHUNK_B,
    }
    _patch_decode_deps(monkeypatch, chunks)

    progress: list[tuple[int, int]] = []
    out = tmp_path / "output.bin"
    fetch_decode_from_ipfs(
        seed_path=tmp_path / "test.sbd",
        out_path=out,
        max_workers=1,
        batch_size=1,
        progress_callback=lambda d, t: (
            progress.append((d, t))
        ),
    )
    assert out.read_bytes() == _CHUNK_A + _CHUNK_B
    assert len(progress) == 2
    assert progress[0] == (1, 2)
    assert progress[1] == (2, 2)


def test_fetch_decode_sha256_mismatch(
    monkeypatch, tmp_path,
) -> None:
    """DecodeError on SHA-256 mismatch."""
    chunks = {_DIGEST_A: _CHUNK_A}
    _patch_decode_deps(
        monkeypatch,
        chunks,
        manifest_sha256="ff" * 32,
    )

    out = tmp_path / "output.bin"
    with pytest.raises(
        DecodeError,
        match="SHA-256 mismatch",
    ):
        fetch_decode_from_ipfs(
            seed_path=tmp_path / "test.sbd",
            out_path=out,
            max_workers=1,
        )


def test_fetch_decode_chunk_unavailable(
    monkeypatch, tmp_path,
) -> None:
    """ExternalToolError when chunk not on IPFS."""
    def _fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "not found",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_raw",
        _fail,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.time.sleep",
        lambda _: None,
    )

    seed = _make_seed([_DIGEST_A])
    seed.manifest["source_sha256"] = "aa" * 32
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.read_seed",
        lambda path, **kw: seed,
    )

    out = tmp_path / "output.bin"
    with pytest.raises(ExternalToolError):
        fetch_decode_from_ipfs(
            seed_path=tmp_path / "test.sbd",
            out_path=out,
            max_workers=1,
        )


def test_fetch_decode_raw_and_ref_mixed(
    monkeypatch, tmp_path,
) -> None:
    """OP_RAW chunks skip IPFS; OP_REF fetched."""
    raw_chunk = b"inline-raw-data"
    chunks = {_DIGEST_B: _CHUNK_B}
    _patch_fetch_deps(monkeypatch, chunks)

    raw_digest = hashlib.sha256(raw_chunk).digest()
    expected = raw_chunk + _CHUNK_B
    source_sha = hashlib.sha256(
        expected,
    ).hexdigest()

    seed = Seed(
        manifest={
            "format": "SBD1",
            "version": 1,
            "source_sha256": source_sha,
        },
        recipe=Recipe(
            hash_table=[raw_digest, _DIGEST_B],
            ops=[
                RecipeOp(
                    opcode=OP_REF,
                    hash_index=0,
                ),
                RecipeOp(
                    opcode=OP_REF,
                    hash_index=1,
                ),
            ],
        ),
        raw_payloads={0: raw_chunk},
        manifest_compression="none",
        signature=None,
        signed_payload=None,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_chunks.read_seed",
        lambda path, **kw: seed,
    )

    out = tmp_path / "output.bin"
    digest = fetch_decode_from_ipfs(
        seed_path=tmp_path / "test.sbd",
        out_path=out,
        max_workers=1,
    )
    assert out.read_bytes() == expected
    assert digest == source_sha


# -- fetch-decode CLI tests ---------------------------------


def test_fetch_decode_cli_basic(
    monkeypatch, tmp_path,
) -> None:
    """CLI fetch-decode succeeds."""
    digest = "aa" * 32

    monkeypatch.setattr(
        "seedbraid.cli.fetch_decode_from_ipfs",
        lambda **kw: digest,
    )

    result = _cli_runner.invoke(
        app,
        [
            "fetch-decode",
            str(tmp_path / "test.sbd"),
            "--out",
            str(tmp_path / "out.bin"),
        ],
    )
    assert result.exit_code == 0
    assert f"decoded sha256={digest}" in (
        result.output
    )


def _raise_fetch_external(**kw):  # noqa: ANN003, ANN202
    raise ExternalToolError(
        "chunk unavailable",
        code="SB_E_IPFS_CHUNK_GET",
        next_action="check ipfs",
    )


def test_fetch_decode_cli_error(
    monkeypatch, tmp_path,
) -> None:
    """CLI exits with code 1 on error."""
    monkeypatch.setattr(
        "seedbraid.cli.fetch_decode_from_ipfs",
        _raise_fetch_external,
    )

    result = _cli_runner.invoke(
        app,
        [
            "fetch-decode",
            str(tmp_path / "test.sbd"),
            "--out",
            str(tmp_path / "out.bin"),
        ],
    )
    assert result.exit_code == 1
    assert "SB_E_IPFS_CHUNK_GET" in result.output


# -- create_chunk_dag tests ---------------------------------


def test_create_chunk_dag_returns_cid(
    monkeypatch,
) -> None:
    """create_chunk_dag returns DAG root CID."""
    expected_cid = "QmDagRoot123"
    void_calls: list[tuple[str, dict]] = []

    def _fake_post_void(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        void_calls.append((path, params))

    def _fake_post_json(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        if path == "/files/stat":
            return {"Hash": expected_cid}
        return {}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_void",
        _fake_post_void,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fake_post_json,
    )

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )
    result = create_chunk_dag(manifest)
    assert result == expected_cid


def test_create_chunk_dag_cleans_up_mfs(
    monkeypatch,
) -> None:
    """MFS entry is cleaned up after stat."""
    void_calls: list[tuple[str, dict]] = []

    def _fake_post_void(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        void_calls.append((path, params))

    def _fake_post_json(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        if path == "/files/stat":
            return {"Hash": "QmRoot"}
        return {}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_void",
        _fake_post_void,
    )
    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fake_post_json,
    )

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )
    create_chunk_dag(manifest)

    rm_calls = [
        (p, kw)
        for p, kw in void_calls
        if p == "/files/rm"
    ]
    assert len(rm_calls) == 1
    assert (
        rm_calls[0][1].get("recursive")
        == "true"
    )


def test_create_chunk_dag_mkdir_failure_raises(
    monkeypatch,
) -> None:
    """ExternalToolError on MFS mkdir failure."""

    def _fail_post_void(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        if path == "/files/mkdir":
            raise ExternalToolError(
                "permission denied",
                code="SB_E_KUBO_API_ERROR",
            )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_void",
        _fail_post_void,
    )

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )
    with pytest.raises(
        ExternalToolError,
        match="MFS directory",
    ) as exc_info:
        create_chunk_dag(manifest)
    assert exc_info.value.code == (
        "SB_E_IPFS_MFS"
    )


# -- pin_dag_locally tests ---------------------------------


def test_pin_dag_locally_success(
    monkeypatch,
) -> None:
    """pin_dag_locally calls kubo pin/add."""
    from seedbraid.ipfs_chunks import (
        pin_dag_locally,
    )

    pin_calls: list[dict] = []

    def _fake_post_json(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        pin_calls.append(params)
        return {"Pins": [params.get("arg", "")]}

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fake_post_json,
    )
    pin_dag_locally("QmTestCid")
    assert len(pin_calls) == 1
    assert pin_calls[0]["arg"] == "QmTestCid"


def test_pin_dag_locally_failure_raises(
    monkeypatch,
) -> None:
    """pin_dag_locally raises on kubo API error."""
    from seedbraid.ipfs_chunks import (
        pin_dag_locally,
    )

    def _fail(
        path, **params,
    ):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "pin timeout",
            code="SB_E_KUBO_API_ERROR",
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.post_json",
        _fail,
    )
    with pytest.raises(
        ExternalToolError,
        match="pin DAG root",
    ) as exc_info:
        pin_dag_locally("QmTestCid")
    assert exc_info.value.code == (
        "SB_E_IPFS_PUBLISH"
    )


# -- publish-chunks CLI pin tests ---------------------------


def test_publish_chunks_cli_with_pin(
    monkeypatch, tmp_path,
) -> None:
    """--pin creates DAG and pins locally."""
    dag_calls: list[str] = []
    pin_calls: list[str] = []

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )

    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        lambda **kw: manifest,
    )
    monkeypatch.setattr(
        "seedbraid.cli.create_chunk_dag",
        lambda m: (
            dag_calls.append("called")
            or "QmDagRoot"
        ),
    )
    monkeypatch.setattr(
        "seedbraid.cli.pin_dag_locally",
        lambda cid: pin_calls.append(cid),
    )
    monkeypatch.setattr(
        "seedbraid.cli.write_chunk_manifest",
        lambda m, p: None,
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(tmp_path / "test.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--pin",
        ],
    )
    assert result.exit_code == 0
    assert len(dag_calls) == 1
    assert pin_calls == ["QmDagRoot"]
    assert "dag_root=QmDagRoot" in (
        result.output
    )


def test_publish_chunks_cli_with_remote_pin(
    monkeypatch, tmp_path,
) -> None:
    """--remote-pin creates DAG and remote pins."""
    from seedbraid.pinning import RemotePinResult

    dag_calls: list[str] = []
    remote_calls: list[str] = []

    manifest = ChunkManifest(
        seed_sha256=_SEED_SHA,
        chunks=(
            _make_chunk_entry(_DIGEST_A),
        ),
    )

    monkeypatch.setattr(
        "seedbraid.cli.publish_chunks_from_genome",
        lambda **kw: manifest,
    )
    monkeypatch.setattr(
        "seedbraid.cli.create_chunk_dag",
        lambda m: (
            dag_calls.append("called")
            or "QmDagRoot"
        ),
    )
    monkeypatch.setattr(
        "seedbraid.cli.remote_pin_cid",
        lambda cid, **kw: (
            remote_calls.append(cid)
            or RemotePinResult(
                provider="psa",
                cid=cid,
                status="pinned",
                request_id="req-1",
            )
        ),
    )
    monkeypatch.setattr(
        "seedbraid.cli.write_chunk_manifest",
        lambda m, p: None,
    )
    monkeypatch.setattr(
        "seedbraid.cli.open_genome",
        lambda p: _MockGenome({}),
    )

    result = _cli_runner.invoke(
        app,
        [
            "publish-chunks",
            str(tmp_path / "test.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--remote-pin",
        ],
    )
    assert result.exit_code == 0
    assert len(dag_calls) == 1
    assert remote_calls == ["QmDagRoot"]
    assert "remote_pin" in result.output
    assert "dag_root=QmDagRoot" in (
        result.output
    )
