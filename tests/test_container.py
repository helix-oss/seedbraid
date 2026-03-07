from __future__ import annotations

import hashlib
import hmac
import json
import struct

import pytest

from helix.container import (
    _V1_HEADER_FMT,
    _V2_HEADER_FMT,
    ENC_MAGIC,
    OP_RAW,
    OP_REF,
    SECTION_INTEGRITY,
    EncryptedEnvelopeInfo,
    Recipe,
    RecipeOp,
    _derive_encryption_keys,
    _keystream,
    _xor_bytes,
    decrypt_seed_bytes,
    encrypt_seed_bytes,
    parse_seed,
    serialize_seed,
    validate_encrypted_seed_envelope,
)
from helix.errors import (
    ACTION_REFETCH_SEED,
    ACTION_UPGRADE_HELIX,
    ACTION_VERIFY_ENCRYPTION,
    ACTION_VERIFY_SEED,
    SeedFormatError,
)


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

    with pytest.raises(SeedFormatError) as exc_info:
        parse_seed(tampered)
    assert "Manifest SHA-256 mismatch" in str(exc_info.value)
    assert exc_info.value.next_action == ACTION_REFETCH_SEED


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


class TestNextAction:
    """Verify next_action is set on representative error paths."""

    def test_short_seed_has_refetch_action(self) -> None:
        with pytest.raises(SeedFormatError) as exc_info:
            parse_seed(b"short")
        assert exc_info.value.next_action == ACTION_REFETCH_SEED

    def test_invalid_magic_has_verify_action(self) -> None:
        blob = b"XXXX" + b"\x00" * 20
        with pytest.raises(SeedFormatError) as exc_info:
            parse_seed(blob)
        assert exc_info.value.next_action == ACTION_VERIFY_SEED

    def test_decrypt_wrong_key_has_verify_encryption_action(
        self,
    ) -> None:
        h1 = bytes.fromhex("aa" * 32)
        recipe = Recipe(
            hash_table=[h1],
            ops=[RecipeOp(opcode=OP_REF, hash_index=0)],
        )
        manifest = {"format": "HLX1", "version": 1}
        seed_bytes = serialize_seed(
            manifest, recipe, {},
            manifest_compression="none",
        )
        encrypted = encrypt_seed_bytes(seed_bytes, "correct")
        with pytest.raises(SeedFormatError) as exc_info:
            decrypt_seed_bytes(encrypted, "wrong")
        assert (
            exc_info.value.next_action
            == ACTION_VERIFY_ENCRYPTION
        )


class TestHLE1V2:
    """HLE1 v2 header, v1 backward compat, and guard tests."""

    def test_v1_encrypted_seed_decryptable(self) -> None:
        """Manually built v1 blob decrypts correctly."""
        passphrase = "legacy-v1-key"
        salt = b"\x01" * 16
        nonce = b"\x02" * 16
        plaintext = b"v1-test-payload-for-compat"

        enc_key, mac_key = _derive_encryption_keys(
            passphrase, salt, n=16384, r=8, p=1,
        )
        ciphertext = _xor_bytes(
            plaintext,
            _keystream(enc_key, nonce, len(plaintext)),
        )

        header = struct.pack(
            _V1_HEADER_FMT,
            ENC_MAGIC, 1,
            len(salt), len(nonce), len(ciphertext),
        )
        payload = header + salt + nonce + ciphertext
        mac = hmac.new(
            mac_key, payload, hashlib.sha256,
        ).digest()
        v1_blob = payload + mac

        result = decrypt_seed_bytes(v1_blob, passphrase)
        assert result == plaintext

    def test_v2_header_scrypt_params_stored(self) -> None:
        """Verify n/r/p bytes in v2 header output."""
        seed_bytes = b"test-payload"
        encrypted = encrypt_seed_bytes(seed_bytes, "key")

        assert encrypted[:4] == ENC_MAGIC
        version = struct.unpack_from(">H", encrypted, 4)[0]
        assert version == 2

        n, r, p, reserved = struct.unpack_from(
            ">IBBH", encrypted, 16,
        )
        assert n == 32768
        assert r == 8
        assert p == 1
        assert reserved == 0

    def test_validate_returns_envelope_info(self) -> None:
        """validate returns EncryptedEnvelopeInfo."""
        seed_bytes = b"info-test"
        encrypted = encrypt_seed_bytes(seed_bytes, "k")
        info = validate_encrypted_seed_envelope(encrypted)
        assert isinstance(info, EncryptedEnvelopeInfo)
        assert info.version == 2
        assert info.header_len == 24
        assert info.scrypt_n == 32768

    def test_scrypt_n_below_minimum_rejected(self) -> None:
        """v2 header with scrypt_n < 16384 is rejected."""
        header = struct.pack(
            _V2_HEADER_FMT,
            ENC_MAGIC, 2,
            16, 16, 10,
            1024, 8, 1, 0,
        )
        blob = header + b"\x00" * (16 + 16 + 10 + 32)
        with pytest.raises(
            SeedFormatError, match="below minimum",
        ):
            validate_encrypted_seed_envelope(blob)

    def test_v2_reserved_nonzero_rejected(self) -> None:
        """v2 header with reserved != 0 is rejected."""
        header = struct.pack(
            _V2_HEADER_FMT,
            ENC_MAGIC, 2,
            16, 16, 10,
            32768, 8, 1, 99,
        )
        blob = header + b"\x00" * (16 + 16 + 10 + 32)
        with pytest.raises(
            SeedFormatError, match="Reserved field",
        ):
            validate_encrypted_seed_envelope(blob)

    def test_unsupported_version_rejected(self) -> None:
        """Version 99 is rejected."""
        header = struct.pack(
            ">4sHBBQ",
            ENC_MAGIC, 99,
            16, 16, 10,
        )
        blob = header + b"\x00" * (16 + 16 + 10 + 32)
        with pytest.raises(
            SeedFormatError, match="Unsupported",
        ) as exc_info:
            validate_encrypted_seed_envelope(blob)
        assert (
            exc_info.value.next_action
            == ACTION_UPGRADE_HELIX
        )
