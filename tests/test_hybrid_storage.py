"""Unit tests for HybridGenomeStorage (no IPFS daemon)."""

from __future__ import annotations

from seedbraid.hybrid_storage import HybridGenomeStorage

_HASH_A = b"\x01" * 32
_DATA_A = b"chunk-alpha"
_HASH_B = b"\x02" * 32
_DATA_B = b"chunk-bravo"
_HASH_C = b"\x03" * 32


class _MockStorage:
    """Dict-backed GenomeStorage mock."""

    def __init__(
        self,
        chunks: dict[bytes, bytes] | None = None,
    ) -> None:
        self._chunks: dict[bytes, bytes] = (
            chunks if chunks is not None else {}
        )
        self._closed = False

    def has_chunk(self, chunk_hash: bytes) -> bool:
        return chunk_hash in self._chunks

    def get_chunk(
        self, chunk_hash: bytes,
    ) -> bytes | None:
        return self._chunks.get(chunk_hash)

    def put_chunk(
        self, chunk_hash: bytes, data: bytes,
    ) -> bool:
        if chunk_hash in self._chunks:
            return False
        self._chunks[chunk_hash] = data
        return True

    def count_chunks(self) -> int:
        return len(self._chunks)

    def close(self) -> None:
        self._closed = True

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(
        self, *a: object,
    ) -> None:
        self.close()


def test_get_chunk_local_hit() -> None:
    local = _MockStorage({_HASH_A: _DATA_A})
    ipfs = _MockStorage({})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    assert hybrid.get_chunk(_HASH_A) == _DATA_A
    assert hybrid.ipfs_hit_count == 0


def test_get_chunk_ipfs_fallback() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({_HASH_A: _DATA_A})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    assert hybrid.get_chunk(_HASH_A) == _DATA_A
    assert hybrid.ipfs_hit_count == 1


def test_get_chunk_cache_fetched_true() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({_HASH_A: _DATA_A})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    hybrid.get_chunk(_HASH_A)
    assert local.has_chunk(_HASH_A) is True


def test_get_chunk_cache_fetched_false() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({_HASH_A: _DATA_A})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=False,
    )
    result = hybrid.get_chunk(_HASH_A)
    assert result == _DATA_A
    assert local.has_chunk(_HASH_A) is False


def test_get_chunk_both_miss() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    assert hybrid.get_chunk(_HASH_C) is None
    assert hybrid.ipfs_hit_count == 0


def test_ipfs_hit_count_increments() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage(
        {_HASH_A: _DATA_A, _HASH_B: _DATA_B},
    )
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=False,
    )
    hybrid.get_chunk(_HASH_A)
    hybrid.get_chunk(_HASH_B)
    assert hybrid.ipfs_hit_count == 2


def test_has_chunk_three_patterns() -> None:
    local = _MockStorage({_HASH_A: _DATA_A})
    ipfs = _MockStorage({_HASH_B: _DATA_B})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    assert hybrid.has_chunk(_HASH_A) is True
    assert hybrid.has_chunk(_HASH_B) is True
    assert hybrid.has_chunk(_HASH_C) is False


def test_put_chunk_local_only() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({})
    hybrid = HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    )
    hybrid.put_chunk(_HASH_A, _DATA_A)
    assert local.has_chunk(_HASH_A) is True
    assert ipfs.has_chunk(_HASH_A) is False


def test_context_manager_closes_both() -> None:
    local = _MockStorage({})
    ipfs = _MockStorage({})
    with HybridGenomeStorage(
        local, ipfs, cache_fetched=True,
    ):
        pass
    assert local._closed is True
    assert ipfs._closed is True
