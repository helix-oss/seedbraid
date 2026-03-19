"""Unit tests for chunk manifest sidecar read/write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seedbraid.chunk_manifest import (
    MANIFEST_FORMAT,
    MANIFEST_VERSION,
    ChunkEntry,
    ChunkManifest,
    manifest_path_for_seed,
    read_chunk_manifest,
    write_chunk_manifest,
)
from seedbraid.errors import SeedbraidError

_SAMPLE_HASH = (
    "b94d27b9934d3e08a52e52d7da7dabfa"
    "c484efe04294e576a3e1d9d8d6e4b7c4"
)
_SAMPLE_CID = (
    "bafkreifzjut3te2nhyekklss27nh3k7"
    "2ysco7y32koao5eei66wof36n5e"
)
_SAMPLE_SEED_SHA = (
    "e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)


def _make_manifest(
    chunks: tuple[ChunkEntry, ...] = (),
    dag_root_cid: str | None = None,
    seed_sha256: str = _SAMPLE_SEED_SHA,
) -> ChunkManifest:
    return ChunkManifest(
        seed_sha256=seed_sha256,
        chunks=chunks,
        dag_root_cid=dag_root_cid,
    )


# -- Round-trip tests --


def test_roundtrip_basic(tmp_path: Path) -> None:
    entry = ChunkEntry(
        hash_hex=_SAMPLE_HASH,
        cid=_SAMPLE_CID,
    )
    m = _make_manifest(chunks=(entry,))
    p = tmp_path / "test.sbd.chunks.json"
    write_chunk_manifest(m, p)
    loaded = read_chunk_manifest(p)
    assert loaded.format == MANIFEST_FORMAT
    assert loaded.version == MANIFEST_VERSION
    assert loaded.seed_sha256 == _SAMPLE_SEED_SHA
    assert len(loaded.chunks) == 1
    assert loaded.chunks[0].hash_hex == _SAMPLE_HASH
    assert loaded.chunks[0].cid == _SAMPLE_CID
    assert loaded.dag_root_cid is None


def test_roundtrip_empty_chunks(
    tmp_path: Path,
) -> None:
    m = _make_manifest()
    p = tmp_path / "empty.json"
    write_chunk_manifest(m, p)
    loaded = read_chunk_manifest(p)
    assert loaded.chunks == ()


def test_roundtrip_dag_root_cid_none(
    tmp_path: Path,
) -> None:
    m = _make_manifest(dag_root_cid=None)
    p = tmp_path / "none_dag.json"
    write_chunk_manifest(m, p)
    loaded = read_chunk_manifest(p)
    assert loaded.dag_root_cid is None


def test_roundtrip_dag_root_cid_set(
    tmp_path: Path,
) -> None:
    dag = (
        "bafybeigdyrzt5sfp7udm7hu76uh7y26"
        "nf3efuylqabf3okuez"
    )
    m = _make_manifest(dag_root_cid=dag)
    p = tmp_path / "dag_set.json"
    write_chunk_manifest(m, p)
    loaded = read_chunk_manifest(p)
    assert loaded.dag_root_cid == dag


def test_roundtrip_multiple_chunks(
    tmp_path: Path,
) -> None:
    entries = tuple(
        ChunkEntry(
            hash_hex=f"{i:0>64x}",
            cid=f"bafkrei{'x' * 50}{i}",
        )
        for i in range(3)
    )
    m = _make_manifest(chunks=entries)
    p = tmp_path / "multi.json"
    write_chunk_manifest(m, p)
    loaded = read_chunk_manifest(p)
    assert len(loaded.chunks) == 3
    for orig, loaded_e in zip(
        entries, loaded.chunks, strict=True
    ):
        assert orig.hash_hex == loaded_e.hash_hex
        assert orig.cid == loaded_e.cid


# -- Path convention tests --


def test_manifest_path_for_seed_sbd() -> None:
    result = manifest_path_for_seed(
        Path("data.sbd"),
    )
    assert result == Path("data.sbd.chunks.json")


def test_manifest_path_for_seed_nested() -> None:
    result = manifest_path_for_seed(
        Path("dir/sub/model.sbd"),
    )
    assert result == Path(
        "dir/sub/model.sbd.chunks.json",
    )


# -- Error tests --


def test_read_invalid_json_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(
        SeedbraidError, match="Cannot read"
    ) as exc_info:
        read_chunk_manifest(p)
    assert exc_info.value.code == (
        "SB_E_CHUNK_MANIFEST_FORMAT"
    )


def test_read_wrong_format_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "wrong_fmt.json"
    p.write_text(
        json.dumps({
            "format": "WRONG",
            "version": 1,
            "chunks": [],
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        SeedbraidError, match="Unknown manifest"
    ) as exc_info:
        read_chunk_manifest(p)
    assert exc_info.value.code == (
        "SB_E_CHUNK_MANIFEST_FORMAT"
    )


def test_read_wrong_version_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "wrong_ver.json"
    p.write_text(
        json.dumps({
            "format": "SBD1-CHUNKS",
            "version": 99,
            "chunks": [],
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        SeedbraidError,
        match="Unsupported.*version",
    ) as exc_info:
        read_chunk_manifest(p)
    assert exc_info.value.code == (
        "SB_E_CHUNK_MANIFEST_FORMAT"
    )


def test_read_missing_format_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "no_fmt.json"
    p.write_text(
        json.dumps({
            "version": 1,
            "chunks": [],
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        SeedbraidError, match="Unknown manifest"
    ):
        read_chunk_manifest(p)


def test_read_missing_chunks_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "no_chunks.json"
    p.write_text(
        json.dumps({
            "format": "SBD1-CHUNKS",
            "version": 1,
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        SeedbraidError, match="chunks.*array"
    ):
        read_chunk_manifest(p)


def test_read_chunk_entry_missing_fields(
    tmp_path: Path,
) -> None:
    p = tmp_path / "bad_entry.json"
    p.write_text(
        json.dumps({
            "format": "SBD1-CHUNKS",
            "version": 1,
            "chunks": [{"hash": "abc"}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(
        SeedbraidError, match="missing.*cid"
    ):
        read_chunk_manifest(p)


def test_read_nonexistent_file_raises(
    tmp_path: Path,
) -> None:
    p = tmp_path / "does_not_exist.json"
    with pytest.raises(
        SeedbraidError, match="Cannot read"
    ):
        read_chunk_manifest(p)


# -- Output format tests --


def test_write_produces_compact_json(
    tmp_path: Path,
) -> None:
    entry = ChunkEntry(
        hash_hex=_SAMPLE_HASH,
        cid=_SAMPLE_CID,
    )
    m = _make_manifest(chunks=(entry,))
    p = tmp_path / "compact.json"
    write_chunk_manifest(m, p)
    text = p.read_text(encoding="utf-8")
    assert ": " not in text
    assert ", " not in text
    parsed = json.loads(text)
    keys = list(parsed.keys())
    assert keys == sorted(keys)


def test_write_creates_parent_dirs(
    tmp_path: Path,
) -> None:
    m = _make_manifest()
    p = tmp_path / "sub" / "nested" / "m.json"
    write_chunk_manifest(m, p)
    assert p.exists()
    loaded = read_chunk_manifest(p)
    assert loaded.format == MANIFEST_FORMAT
