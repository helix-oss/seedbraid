from __future__ import annotations

import functools
import hashlib
import io

from seedbraid.chunking import (
    ChunkerConfig,
    chunk_bytes,
    iter_cdc_buzhash,
    iter_cdc_rabin,
)

_CFG_SHIFT = ChunkerConfig(
    min_size=512, avg_size=2048, max_size=8192, window_size=32
)
_INSERT_OFFSET = 10_000
_DATA_BLOCKS = 4_000  # SHA-256 blocks (125 KiB)


def test_cdc_buzhash_deterministic_boundaries() -> None:
    data = (b"A" * 100_000) + (b"B" * 120_000) + (b"1234567890" * 5_000)
    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    first = chunk_bytes(data, "cdc_buzhash", cfg)
    second = chunk_bytes(data, "cdc_buzhash", cfg)

    assert first == second


def test_cdc_rabin_deterministic_boundaries() -> None:
    data = (b"xyz" * 90_000) + b"!" + (b"xyz" * 90_000)
    cfg = ChunkerConfig(
        min_size=1024, avg_size=4096, max_size=16384, window_size=32
    )

    first = chunk_bytes(data, "cdc_rabin", cfg)
    second = chunk_bytes(data, "cdc_rabin", cfg)

    assert first == second


@functools.lru_cache(maxsize=1)
def _make_data() -> bytes:
    return b"".join(
        hashlib.sha256(i.to_bytes(4, "big")).digest()
        for i in range(_DATA_BLOCKS)
    )


@functools.lru_cache(maxsize=1)
def _make_shifted() -> bytes:
    data = _make_data()
    return (
        data[:_INSERT_OFFSET]
        + b"\xff"
        + data[_INSERT_OFFSET:]
    )


def _chunks_before_offset(
    chunks: list[bytes], offset: int
) -> list[bytes]:
    result: list[bytes] = []
    pos = 0
    for c in chunks:
        if pos + len(c) <= offset:
            result.append(c)
            pos += len(c)
        else:
            break
    return result


def _assert_prefix_invariant(chunker_fn) -> None:
    """Chunks before the 1-byte insert point stay identical."""
    data = _make_data()
    shifted = _make_shifted()

    orig = list(
        chunker_fn(io.BytesIO(data), _CFG_SHIFT)
    )
    shifted_chunks = list(
        chunker_fn(io.BytesIO(shifted), _CFG_SHIFT)
    )

    assert len(orig) >= 2, "Not enough chunks to test"

    pre_orig = _chunks_before_offset(
        orig, _INSERT_OFFSET
    )
    pre_shifted = _chunks_before_offset(
        shifted_chunks, _INSERT_OFFSET
    )

    assert len(pre_orig) >= 1, (
        "No chunks before insert point"
    )
    assert pre_orig == pre_shifted, (
        "Chunks before insert point changed"
        " after insertion"
    )


def test_cdc_buzhash_shift_resilient_prefix() -> None:
    _assert_prefix_invariant(iter_cdc_buzhash)


def test_cdc_rabin_shift_resilient_prefix() -> None:
    _assert_prefix_invariant(iter_cdc_rabin)


def test_cdc_buzhash_shift_resilient_suffix_reuse() -> None:
    """BuzHash: most chunks are reused after 1-byte insert."""
    data = _make_data()
    shifted = _make_shifted()

    orig = list(
        iter_cdc_buzhash(io.BytesIO(data), _CFG_SHIFT)
    )
    shifted_chunks = list(
        iter_cdc_buzhash(io.BytesIO(shifted), _CFG_SHIFT)
    )

    orig_set = set(orig)
    reuse_count = len(orig_set & set(shifted_chunks))
    total = len(orig_set)

    assert total >= 2, "Not enough unique chunks"
    # Allow up to 3 chunks to differ: 1-byte insertion
    # affects only the chunk straddling the insert point
    # plus at most 2 neighbours before CDC re-converges.
    assert reuse_count >= total - 3, (
        f"Too few reused chunks: {reuse_count}/{total}"
    )
