from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from math import log2
from typing import BinaryIO

MASK64 = (1 << 64) - 1


@dataclass(frozen=True)
class ChunkerConfig:
    min_size: int = 16_384
    avg_size: int = 65_536
    max_size: int = 262_144
    window_size: int = 64


def _iter_bytes(stream: BinaryIO, read_size: int = 65_536) -> Iterator[int]:
    while True:
        block = stream.read(read_size)
        if not block:
            return
        yield from block


def _mask_from_avg(avg_size: int) -> int:
    bits = max(1, round(log2(max(2, avg_size))))
    return (1 << bits) - 1


def _rotl64(value: int, shift: int) -> int:
    shift %= 64
    return ((value << shift) | (value >> (64 - shift))) & MASK64


def iter_fixed_chunks(stream: BinaryIO, chunk_size: int) -> Iterator[bytes]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        yield chunk


def _buzhash_table() -> list[int]:
    # Deterministic constants generated once and inlined.
    return [
        0x4A3B2C1D0E0F1234, 0x9E3779B97F4A7C15,
        0xD1B54A32D192ED03, 0x94D049BB133111EB,
        0x8538ECB5BD456EA3, 0xCA5A826395121157,
        0xA4093822299F31D0, 0x13198A2E03707344,
        0x243F6A8885A308D3, 0x3BD39E10CB0EF593,
        0xC0AC29B7C97C50DD, 0xBE5466CF34E90C6C,
        0x452821E638D01377, 0x7EF84F78FD955CB1,
        0x1A2B3C4D5E6F7081, 0xABC98388FB8FAC03,
    ] * 16


def iter_cdc_buzhash(stream: BinaryIO, cfg: ChunkerConfig) -> Iterator[bytes]:
    table = _buzhash_table()
    window = [0] * cfg.window_size
    window_fill = 0
    wpos = 0
    h = 0
    mask = _mask_from_avg(cfg.avg_size)
    out = bytearray()

    for b in _iter_bytes(stream):
        out.append(b)
        if window_fill < cfg.window_size:
            window[window_fill] = b
            window_fill += 1
            h = _rotl64(h, 1) ^ table[b]
        else:
            old = window[wpos]
            window[wpos] = b
            wpos = (wpos + 1) % cfg.window_size
            h = _rotl64(h, 1) ^ table[b] ^ _rotl64(table[old], cfg.window_size)

        size = len(out)
        if size < cfg.min_size:
            continue
        if size >= cfg.max_size or (h & mask) == 0:
            yield bytes(out)
            out.clear()

    if out:
        yield bytes(out)


def iter_cdc_rabin(stream: BinaryIO, cfg: ChunkerConfig) -> Iterator[bytes]:
    base = 257
    window = [0] * cfg.window_size
    window_fill = 0
    wpos = 0
    h = 0
    base_pow = pow(base, cfg.window_size, 1 << 64)
    mask = _mask_from_avg(cfg.avg_size)
    out = bytearray()

    for b in _iter_bytes(stream):
        out.append(b)
        if window_fill < cfg.window_size:
            window[window_fill] = b
            window_fill += 1
            h = ((h * base) + b) & MASK64
        else:
            old = window[wpos]
            window[wpos] = b
            wpos = (wpos + 1) % cfg.window_size
            h = (h - (old * base_pow)) & MASK64
            h = ((h * base) + b) & MASK64

        size = len(out)
        if size < cfg.min_size:
            continue
        if size >= cfg.max_size or (h & mask) == 0:
            yield bytes(out)
            out.clear()

    if out:
        yield bytes(out)


def iter_chunks(
    stream: BinaryIO, chunker: str, cfg: ChunkerConfig,
) -> Iterator[bytes]:
    if chunker == "fixed":
        yield from iter_fixed_chunks(stream, cfg.avg_size)
        return
    if chunker == "cdc_buzhash":
        yield from iter_cdc_buzhash(stream, cfg)
        return
    if chunker == "cdc_rabin":
        yield from iter_cdc_rabin(stream, cfg)
        return
    raise ValueError(f"Unsupported chunker: {chunker}")


def chunk_bytes(data: bytes, chunker: str, cfg: ChunkerConfig) -> list[int]:
    from io import BytesIO

    with BytesIO(data) as bio:
        return [len(c) for c in iter_chunks(bio, chunker, cfg)]
