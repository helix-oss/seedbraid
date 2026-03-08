from __future__ import annotations

import hashlib
import hmac
import json
import struct

import pytest

from seedbraid.container import (
    _V1_HEADER_FMT,
    _V2_HEADER_FMT,
    _V3_HEADER_SIZE,
    AEAD_NONCE_LEN,
    ALGO_AES_256_GCM,
    ENC_MAGIC,
    OP_RAW,
    OP_REF,
    SECTION_INTEGRITY,
    EncryptedEnvelopeInfo,
    Recipe,
    RecipeOp,
    _derive_aead_key,
    _derive_encryption_keys,
    _encrypt_v2,
    _keystream,
    _xor_bytes,
    decrypt_seed_bytes,
    encrypt_seed_bytes,
    parse_seed,
    serialize_seed,
    validate_encrypted_seed_envelope,
)
from seedbraid.errors import (
    ACTION_REFETCH_SEED,
    ACTION_UPGRADE_SEEDBRAID,
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
        "format": "SBD1",
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
        "format": "SBD1",
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
        manifest = {"format": "SBD1", "version": 1}
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


class TestSBE1V2:
    """SBE1 v2 header, v1 backward compat, and guard tests."""

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
        encrypted = _encrypt_v2(seed_bytes, "key")

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

    def test_validate_returns_envelope_info_v2(self) -> None:
        """validate returns EncryptedEnvelopeInfo for v2."""
        seed_bytes = b"info-test"
        encrypted = _encrypt_v2(seed_bytes, "k")
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
            == ACTION_UPGRADE_SEEDBRAID
        )


class TestSBE1V3:
    """SBE1 v3 AEAD (AES-256-GCM) tests."""

    def test_v3_roundtrip(self) -> None:
        """v3 encrypt -> decrypt roundtrip."""
        plaintext = b"aead-roundtrip-test-payload"
        encrypted = encrypt_seed_bytes(plaintext, "pw")
        assert encrypted[:4] == ENC_MAGIC
        version = struct.unpack_from(">H", encrypted, 4)[0]
        assert version == 3
        result = decrypt_seed_bytes(encrypted, "pw")
        assert result == plaintext

    def test_v3_header_fields(self) -> None:
        """Verify v3 header fields."""
        encrypted = encrypt_seed_bytes(b"hdr", "k")
        info = validate_encrypted_seed_envelope(encrypted)
        assert info.version == 3
        assert info.header_len == _V3_HEADER_SIZE
        assert info.algo_id == ALGO_AES_256_GCM
        assert info.nonce_len == AEAD_NONCE_LEN
        assert info.scrypt_n == 32768

    def test_v3_tampered_ciphertext_rejected(self) -> None:
        """Tampered ciphertext fails AEAD auth."""
        encrypted = encrypt_seed_bytes(b"tamper-ct", "k")
        ba = bytearray(encrypted)
        ba[-17] ^= 0xFF
        with pytest.raises(
            SeedFormatError, match="authentication failed",
        ):
            decrypt_seed_bytes(bytes(ba), "k")

    def test_v3_tampered_header_rejected(self) -> None:
        """Tampered header (AAD) fails AEAD auth."""
        encrypted = encrypt_seed_bytes(b"tamper-hdr", "k")
        # Tamper scrypt_r (offset 24) — passes validation
        # but changes AAD, causing AEAD auth failure.
        ba = bytearray(encrypted)
        ba[24] = 9  # r=9 instead of 8
        with pytest.raises(
            SeedFormatError, match="authentication failed",
        ):
            decrypt_seed_bytes(bytes(ba), "k")

    def test_v3_wrong_passphrase_rejected(self) -> None:
        """Wrong passphrase fails AEAD auth."""
        encrypted = encrypt_seed_bytes(b"wrong-pw", "correct")
        with pytest.raises(
            SeedFormatError, match="authentication failed",
        ):
            decrypt_seed_bytes(encrypted, "wrong")

    def test_v3_unknown_algo_rejected(self) -> None:
        """Unknown algo_id is rejected at validation."""
        encrypted = encrypt_seed_bytes(b"algo", "k")
        ba = bytearray(encrypted)
        ba[6] = 0xFF  # invalid algo_id
        with pytest.raises(
            SeedFormatError, match="Unknown encryption",
        ):
            validate_encrypted_seed_envelope(bytes(ba))

    def test_v3_reserved_nonzero_rejected(self) -> None:
        """v3 reserved field nonzero is rejected."""
        encrypted = encrypt_seed_bytes(b"res", "k")
        ba = bytearray(encrypted)
        ba[9] = 0x01  # reserved_a
        with pytest.raises(
            SeedFormatError, match="non-zero",
        ):
            validate_encrypted_seed_envelope(bytes(ba))

    def test_v3_reserved2_nonzero_rejected(self) -> None:
        """v3 reserved2 field nonzero is rejected."""
        encrypted = encrypt_seed_bytes(b"res2", "k")
        ba = bytearray(encrypted)
        ba[26] = 0x01  # reserved2 high byte
        with pytest.raises(
            SeedFormatError, match="non-zero",
        ):
            validate_encrypted_seed_envelope(bytes(ba))

    def test_v3_truncated_rejected(self) -> None:
        """Truncated v3 blob is rejected."""
        encrypted = encrypt_seed_bytes(b"trunc", "k")
        with pytest.raises(SeedFormatError):
            validate_encrypted_seed_envelope(
                encrypted[:20],
            )

    def test_hkdf_deterministic(self) -> None:
        """Same inputs produce same AEAD key."""
        salt = b"\xaa" * 16
        k1 = _derive_aead_key("pass", salt)
        k2 = _derive_aead_key("pass", salt)
        assert k1 == k2
        assert len(k1) == 32

    def test_v3_empty_plaintext(self) -> None:
        """v3 handles zero-length plaintext."""
        encrypted = encrypt_seed_bytes(b"", "k")
        result = decrypt_seed_bytes(encrypted, "k")
        assert result == b""

    def test_v2_still_decryptable(self) -> None:
        """v2 blobs remain decryptable after v3 code."""
        plaintext = b"v2-compat"
        v2_blob = _encrypt_v2(plaintext, "v2key")
        result = decrypt_seed_bytes(v2_blob, "v2key")
        assert result == plaintext
