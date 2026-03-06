from __future__ import annotations

from helix.chunking import ChunkerConfig, chunk_bytes


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
