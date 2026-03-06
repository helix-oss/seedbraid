from __future__ import annotations

import json
import struct

import pytest

from helix.container import (
    OP_RAW,
    OP_REF,
    SECTION_INTEGRITY,
    Recipe,
    RecipeOp,
    parse_seed,
    serialize_seed,
)
from helix.errors import SeedFormatError


def test_seed_serialize_parse_serialize_stable() -> None:
    h1 = bytes.fromhex("00" * 32)
    h2 = bytes.fromhex("11" * 32)
    recipe = Recipe(
        hash_table=[h1, h2],
        ops=[
            RecipeOp(opcode=OP_REF, hash_index=0),
            RecipeOp(opcode=OP_RAW, hash_index=1),
        ],
    )
    manifest = {
        "format": "HLX1",
        "version": 1,
        "source_size": 5,
        "source_sha256": "deadbeef",
        "chunker": {
            "name": "fixed",
            "min": 1,
            "avg": 1,
            "max": 1,
            "window_size": 0,
        },
        "portable": True,
        "learn": False,
        "stats": {
            "total_chunks": 2,
            "reused_chunks": 1,
            "new_chunks": 1,
            "raw_chunks": 1,
        },
        "created_at": "2026-02-08T00:00:00+00:00",
    }
    raw = {1: b"abc"}

    blob1 = serialize_seed(manifest, recipe, raw, manifest_compression="zlib")
    parsed = parse_seed(blob1)
    blob2 = serialize_seed(
        parsed.manifest,
        parsed.recipe,
        parsed.raw_payloads,
        manifest_compression=parsed.manifest_compression,
    )

    assert blob1 == blob2


def test_seed_integrity_detects_manifest_sha256_mismatch() -> None:
    h1 = bytes.fromhex("22" * 32)
    recipe = Recipe(
        hash_table=[h1], ops=[RecipeOp(opcode=OP_REF, hash_index=0)]
    )
    manifest = {
        "format": "HLX1",
        "version": 1,
        "source_size": 1,
        "source_sha256": "ab",
        "chunker": {
            "name": "fixed",
            "min": 1,
            "avg": 1,
            "max": 1,
            "window_size": 0,
        },
        "portable": False,
        "learn": True,
        "stats": {
            "total_chunks": 1,
            "reused_chunks": 1,
            "new_chunks": 0,
            "raw_chunks": 0,
        },
        "created_at": "2026-02-08T00:00:00+00:00",
    }
    seed = serialize_seed(manifest, recipe, {}, manifest_compression="zlib")
    tampered = _tamper_integrity_field(seed, "manifest_sha256", "0" * 64)

    with pytest.raises(SeedFormatError, match="Manifest SHA-256 mismatch"):
        parse_seed(tampered)


def _tamper_integrity_field(seed_blob: bytes, key: str, value: str) -> bytes:
    magic, version, section_count = struct.unpack_from(">4sHH", seed_blob, 0)
    offset = 8
    sections: list[tuple[int, bytes]] = []

    for _ in range(section_count):
        stype, length = struct.unpack_from(">HQ", seed_blob, offset)
        offset += 10
        payload = seed_blob[offset : offset + length]
        offset += length
        if stype == SECTION_INTEGRITY:
            integrity = json.loads(payload.decode("utf-8"))
            integrity[key] = value
            payload = json.dumps(
                integrity,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        sections.append((stype, payload))

    out = bytearray(struct.pack(">4sHH", magic, version, section_count))
    for stype, payload in sections:
        out.extend(struct.pack(">HQ", stype, len(payload)))
        out.extend(payload)
    return bytes(out)
