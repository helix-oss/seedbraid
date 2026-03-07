"""HLX1 binary seed container.

Handles serialization, parsing, encryption, and signature for the
TLV section format defined in FORMAT.md, including manifest
compression, recipe encoding, raw payloads, integrity checks, and
the HLE1 encrypted envelope.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import (
    ACTION_CHECK_OPTIONS,
    ACTION_INSTALL_CRYPTO,
    ACTION_INSTALL_ZSTD,
    ACTION_PROVIDE_ENCRYPTION_KEY,
    ACTION_REFETCH_SEED,
    ACTION_REGENERATE_SEED,
    ACTION_REPORT_BUG,
    ACTION_UPGRADE_HELIX,
    ACTION_VERIFY_ENCRYPTION,
    ACTION_VERIFY_SEED,
    SeedFormatError,
)

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,
    )
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False

MAGIC = b"HLX1"
VERSION = 1
ENC_MAGIC = b"HLE1"
ENC_VERSION = 2

SCRYPT_N_DEFAULT = 32768
SCRYPT_N_V1 = 16384  # fixed n for HLE1 v1 header
SCRYPT_N_MIN = 16384
SCRYPT_R_DEFAULT = 8
SCRYPT_P_DEFAULT = 1

_V1_HEADER_FMT = ">4sHBBQ"
_V2_HEADER_FMT = ">4sHBBQIBBH"
_V3_HEADER_FMT = ">4sHBBBBBBQIBBH"
_V3_HEADER_SIZE = 28

ENC_VERSION_V3 = 3
ALGO_AES_256_GCM = 0x01
ALGO_CHACHA20_POLY1305 = 0x02
AEAD_NONCE_LEN = 12
AEAD_TAG_LEN = 16

_HKDF_INFO = b"helix-hle1-v3-aead-key"

SECTION_MANIFEST = 1
SECTION_RECIPE = 2
SECTION_RAW = 3
SECTION_INTEGRITY = 4
SECTION_SIGNATURE = 5

OP_REF = 1
OP_RAW = 2

COMPRESS_NONE = 0
COMPRESS_ZLIB = 1
COMPRESS_ZSTD = 2

_COMPRESSION_NAME_TO_ID = {
    "none": COMPRESS_NONE,
    "zlib": COMPRESS_ZLIB,
    "zstd": COMPRESS_ZSTD,
}
_COMPRESSION_ID_TO_NAME = {
    v: k for k, v in _COMPRESSION_NAME_TO_ID.items()
}


@dataclass(frozen=True)
class RecipeOp:
    opcode: int
    hash_index: int


@dataclass(frozen=True)
class Recipe:
    hash_table: list[bytes]
    ops: list[RecipeOp]


@dataclass(frozen=True)
class Seed:
    manifest: dict[str, Any]
    recipe: Recipe
    raw_payloads: dict[int, bytes]
    manifest_compression: str
    signature: dict[str, Any] | None
    signed_payload: bytes | None


def _compress(data: bytes, name: str) -> bytes:
    if name == "none":
        return data
    if name == "zlib":
        return zlib.compress(data)
    if name == "zstd":
        try:
            import zstandard as zstd
        except ImportError as exc:
            raise SeedFormatError(
                "Compression 'zstd' requires optional"
                " dependency 'zstandard'.",
                next_action=ACTION_INSTALL_ZSTD,
            ) from exc
        return zstd.ZstdCompressor(level=3).compress(data)  # type: ignore[no-any-return]
    raise SeedFormatError(
        f"Unsupported compression: {name}",
        next_action=ACTION_CHECK_OPTIONS,
    )


def _decompress(data: bytes, ctype: int) -> bytes:
    if ctype == COMPRESS_NONE:
        return data
    if ctype == COMPRESS_ZLIB:
        return zlib.decompress(data)
    if ctype == COMPRESS_ZSTD:
        try:
            import zstandard as zstd
        except ImportError as exc:
            raise SeedFormatError(
                "Seed uses zstd compression but"
                " 'zstandard' is not installed.",
                next_action=ACTION_INSTALL_ZSTD,
            ) from exc
        return zstd.ZstdDecompressor().decompress(data)  # type: ignore[no-any-return]
    raise SeedFormatError(
        f"Unknown manifest compression id: {ctype}",
        next_action=ACTION_REGENERATE_SEED,
    )


def encode_recipe(recipe: Recipe) -> bytes:
    """Serialize a recipe to binary format.

    Encodes the hash table and op stream per the
    FORMAT.md recipe section specification.

    Args:
        recipe: Recipe containing a hash table of
            32-byte SHA-256 digests and a list of
            ops.

    Returns:
        Binary-encoded recipe bytes.

    Raises:
        SeedFormatError: If any hash table entry is
            not exactly 32 bytes.
    """
    out = bytearray()
    out.extend(struct.pack(">II", len(recipe.ops), len(recipe.hash_table)))
    for digest in recipe.hash_table:
        if len(digest) != 32:
            raise SeedFormatError(
                "Recipe hash table must contain"
                " 32-byte SHA-256 digests.",
                next_action=ACTION_REPORT_BUG,
            )
        out.extend(digest)
    for op in recipe.ops:
        out.extend(struct.pack(">BI", op.opcode, op.hash_index))
    return bytes(out)


def decode_recipe(data: bytes) -> Recipe:
    """Deserialize a recipe from binary format.

    Parses the hash table and op stream, validating
    opcodes and index bounds.

    Args:
        data: Raw bytes of the recipe section.

    Returns:
        Decoded ``Recipe`` with hash table and ops.

    Raises:
        SeedFormatError: If the data is truncated,
            contains unknown opcodes, or has out-of-
            bounds hash indices.
    """
    if len(data) < 8:
        raise SeedFormatError(
            "Recipe section too short.",
            next_action=ACTION_VERIFY_SEED,
        )
    op_count, hash_count = struct.unpack_from(">II", data, 0)
    offset = 8
    hash_table: list[bytes] = []
    for _ in range(hash_count):
        if offset + 32 > len(data):
            raise SeedFormatError(
                "Recipe hash table truncated.",
                next_action=ACTION_VERIFY_SEED,
            )
        hash_table.append(data[offset : offset + 32])
        offset += 32

    ops: list[RecipeOp] = []
    for _ in range(op_count):
        if offset + 5 > len(data):
            raise SeedFormatError(
                "Recipe op stream truncated.",
                next_action=ACTION_VERIFY_SEED,
            )
        opcode, index = struct.unpack_from(">BI", data, offset)
        offset += 5
        if opcode not in (OP_REF, OP_RAW):
            raise SeedFormatError(
                f"Unknown recipe opcode: {opcode}",
                next_action=ACTION_REGENERATE_SEED,
            )
        if index >= hash_count:
            raise SeedFormatError(
                "Recipe op hash index out of bounds.",
                next_action=ACTION_REGENERATE_SEED,
            )
        ops.append(RecipeOp(opcode=opcode, hash_index=index))

    if offset != len(data):
        raise SeedFormatError(
            "Recipe section has trailing bytes.",
            next_action=ACTION_VERIFY_SEED,
        )
    return Recipe(hash_table=hash_table, ops=ops)


def encode_raw_payloads(raw_payloads: dict[int, bytes]) -> bytes:
    """Serialize RAW payloads to binary format.

    Entries are written in ascending index order.

    Args:
        raw_payloads: Map of hash-table index to
            embedded chunk data.

    Returns:
        Binary-encoded RAW section bytes.
    """
    out = bytearray(struct.pack(">I", len(raw_payloads)))
    for index in sorted(raw_payloads):
        payload = raw_payloads[index]
        out.extend(struct.pack(">II", index, len(payload)))
        out.extend(payload)
    return bytes(out)


def decode_raw_payloads(data: bytes) -> dict[int, bytes]:
    """Deserialize RAW payloads from binary format.

    Args:
        data: Raw bytes of the RAW section.

    Returns:
        Map of hash-table index to chunk data.

    Raises:
        SeedFormatError: If the section is truncated
            or has trailing bytes.
    """
    if len(data) < 4:
        raise SeedFormatError(
            "RAW section too short.",
            next_action=ACTION_VERIFY_SEED,
        )
    count = struct.unpack_from(">I", data, 0)[0]
    offset = 4
    raw: dict[int, bytes] = {}
    for _ in range(count):
        if offset + 8 > len(data):
            raise SeedFormatError(
                "RAW section entry header truncated.",
                next_action=ACTION_VERIFY_SEED,
            )
        index, size = struct.unpack_from(">II", data, offset)
        offset += 8
        if offset + size > len(data):
            raise SeedFormatError(
                "RAW section entry payload truncated.",
                next_action=ACTION_VERIFY_SEED,
            )
        raw[index] = data[offset : offset + size]
        offset += size
    if offset != len(data):
        raise SeedFormatError(
            "RAW section has trailing bytes.",
            next_action=ACTION_VERIFY_SEED,
        )
    return raw


def _pack_section(stype: int, payload: bytes) -> bytes:
    return struct.pack(">HQ", stype, len(payload)) + payload


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256_hex(data: bytes, key: str) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _scrypt_base_key(
    passphrase: str,
    salt: bytes,
    *,
    n: int = SCRYPT_N_DEFAULT,
    r: int = SCRYPT_R_DEFAULT,
    p: int = SCRYPT_P_DEFAULT,
) -> bytes:
    """Derive 32-byte base key via scrypt."""
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=32,
        maxmem=256 * r * n + 1024 * 1024,
    )


def _derive_encryption_keys(
    passphrase: str,
    salt: bytes,
    *,
    n: int = SCRYPT_N_DEFAULT,
    r: int = SCRYPT_R_DEFAULT,
    p: int = SCRYPT_P_DEFAULT,
) -> tuple[bytes, bytes]:
    base_key = _scrypt_base_key(
        passphrase, salt, n=n, r=r, p=p,
    )
    enc_key = hashlib.sha256(base_key + b"enc").digest()
    mac_key = hashlib.sha256(base_key + b"mac").digest()
    return enc_key, mac_key


def _derive_aead_key(
    passphrase: str,
    salt: bytes,
    *,
    n: int = SCRYPT_N_DEFAULT,
    r: int = SCRYPT_R_DEFAULT,
    p: int = SCRYPT_P_DEFAULT,
) -> bytes:
    """Derive a 32-byte AEAD key via scrypt + HKDF-SHA256."""
    base_key = _scrypt_base_key(
        passphrase, salt, n=n, r=r, p=p,
    )
    hkdf = HKDFExpand(
        algorithm=SHA256(),
        length=32,
        info=_HKDF_INFO,
    )
    return hkdf.derive(base_key)


def _encrypt_aead(
    plaintext: bytes,
    key: bytes,
    nonce: bytes,
    aad: bytes,
) -> bytes:
    """Encrypt with AES-256-GCM. Returns ciphertext + 16-byte tag."""
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def _decrypt_aead(
    ciphertext_with_tag: bytes,
    key: bytes,
    nonce: bytes,
    aad: bytes,
) -> bytes:
    """Decrypt AES-256-GCM. Raises SeedFormatError on auth failure."""
    try:
        return AESGCM(key).decrypt(
            nonce, ciphertext_with_tag, aad,
        )
    except InvalidTag as exc:
        raise SeedFormatError(
            "Encrypted seed authentication failed"
            " (wrong key or tampering).",
            next_action=ACTION_VERIFY_ENCRYPTION,
        ) from exc


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    blocks: list[bytes] = []
    produced = 0
    counter = 0
    while produced < length:
        block = hashlib.sha256(
            enc_key + nonce + counter.to_bytes(8, "big")
        ).digest()
        blocks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=False))


def is_encrypted_seed_data(data: bytes) -> bool:
    """Check whether raw bytes begin with the HLE1 magic.

    Only inspects the first four bytes; does not
    validate the full envelope.

    Args:
        data: Raw seed bytes to inspect.

    Returns:
        ``True`` if ``data`` starts with the HLE1
        encrypted seed magic bytes.
    """
    return len(data) >= 4 and data[:4] == ENC_MAGIC


@dataclass(frozen=True)
class EncryptedEnvelopeInfo:
    version: int
    header_len: int
    salt_len: int
    nonce_len: int
    ciphertext_len: int
    scrypt_n: int
    scrypt_r: int
    scrypt_p: int
    algo_id: int = 0


def validate_encrypted_seed_envelope(
    blob: bytes,
) -> EncryptedEnvelopeInfo:
    """Validate the structure of an HLE1 envelope.

    Checks magic, version, header fields, scrypt
    parameter minimums (v2+), and overall length
    consistency.  Supports v1, v2, and v3 headers.

    Args:
        blob: Complete encrypted seed bytes
            including the trailing MAC.

    Returns:
        Parsed envelope metadata with header
        dimensions and KDF parameters.

    Raises:
        SeedFormatError: If the magic is wrong, the
            version is unsupported, scrypt ``n`` is
            below the minimum, or lengths are
            inconsistent.
    """
    if len(blob) < 6:
        raise SeedFormatError(
            "Encrypted seed is too short.",
            next_action=ACTION_REFETCH_SEED,
        )
    magic, version = struct.unpack_from(">4sH", blob, 0)
    if magic != ENC_MAGIC:
        raise SeedFormatError(
            "Encrypted seed magic mismatch."
            " Expected HLE1.",
            next_action=ACTION_REFETCH_SEED,
        )

    algo_id = 0
    if version == 1:
        if len(blob) < 16 + 32:
            raise SeedFormatError(
                "Encrypted seed v1 header"
                " truncated.",
                next_action=ACTION_REFETCH_SEED,
            )
        (
            _, _, salt_len, nonce_len, ciphertext_len,
        ) = struct.unpack_from(_V1_HEADER_FMT, blob, 0)
        header_len = 16
        scrypt_n = SCRYPT_N_V1
        scrypt_r = SCRYPT_R_DEFAULT
        scrypt_p = SCRYPT_P_DEFAULT
    elif version == 2:
        if len(blob) < 24 + 32:
            raise SeedFormatError(
                "Encrypted seed v2 header"
                " truncated.",
                next_action=ACTION_REFETCH_SEED,
            )
        (
            _, _, salt_len, nonce_len, ciphertext_len,
            scrypt_n, scrypt_r, scrypt_p, reserved,
        ) = struct.unpack_from(_V2_HEADER_FMT, blob, 0)
        if reserved != 0:
            raise SeedFormatError(
                "Reserved field in encrypted"
                " seed header is non-zero.",
                next_action=ACTION_UPGRADE_HELIX,
            )
        header_len = 24
    elif version == 3:
        if len(blob) < _V3_HEADER_SIZE:
            raise SeedFormatError(
                "Encrypted seed v3 header"
                " truncated.",
                next_action=ACTION_REFETCH_SEED,
            )
        (
            _, _, algo_id, salt_len, nonce_len,
            res_a, res_b, res_c,
            ciphertext_len,
            scrypt_n, scrypt_r, scrypt_p, reserved2,
        ) = struct.unpack_from(_V3_HEADER_FMT, blob, 0)
        if algo_id not in (
            ALGO_AES_256_GCM,
            ALGO_CHACHA20_POLY1305,
        ):
            raise SeedFormatError(
                "Unknown encryption algorithm"
                f" id: {algo_id}",
                next_action=ACTION_UPGRADE_HELIX,
            )
        if res_a != 0 or res_b != 0 or res_c != 0:
            raise SeedFormatError(
                "Reserved field in encrypted"
                " seed v3 header is non-zero.",
                next_action=ACTION_UPGRADE_HELIX,
            )
        if reserved2 != 0:
            raise SeedFormatError(
                "Reserved field in encrypted"
                " seed v3 header is non-zero.",
                next_action=ACTION_UPGRADE_HELIX,
            )
        header_len = _V3_HEADER_SIZE
    else:
        raise SeedFormatError(
            "Unsupported encrypted seed"
            f" version: {version}",
            next_action=ACTION_UPGRADE_HELIX,
        )

    if version >= 2 and scrypt_n < SCRYPT_N_MIN:
        raise SeedFormatError(
            f"scrypt n={scrypt_n} below"
            f" minimum {SCRYPT_N_MIN};"
            " possible downgrade attack.",
            next_action=ACTION_REFETCH_SEED,
        )

    mac_len = 32 if version <= 2 else 0
    expected_len = (
        header_len + salt_len + nonce_len
        + ciphertext_len + mac_len
    )
    if len(blob) != expected_len:
        raise SeedFormatError(
            "Encrypted seed length mismatch"
            " or truncation detected.",
            next_action=ACTION_REFETCH_SEED,
        )
    return EncryptedEnvelopeInfo(
        version=version,
        header_len=header_len,
        salt_len=salt_len,
        nonce_len=nonce_len,
        ciphertext_len=ciphertext_len,
        scrypt_n=scrypt_n,
        scrypt_r=scrypt_r,
        scrypt_p=scrypt_p,
        algo_id=algo_id,
    )


def _build_signature_payload(
    signed_payload: bytes,
    signature_key: str,
    key_id: str,
) -> bytes:
    signature = {
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "signed_payload_sha256": _sha256_hex(signed_payload),
        "signature": _hmac_sha256_hex(signed_payload, signature_key),
    }
    return json.dumps(
        signature, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def encrypt_seed_bytes(seed_bytes: bytes, passphrase: str) -> bytes:
    """Encrypt seed bytes into an HLE1 envelope.

    When the ``cryptography`` package is available,
    produces a v3 envelope using AES-256-GCM with
    HKDF key derivation.  Otherwise falls back to
    v2 format with the legacy stream cipher.

    Args:
        seed_bytes: Plaintext HLX1 seed bytes.
        passphrase: Passphrase for key derivation.

    Returns:
        HLE1 envelope bytes (v3 or v2 depending on
        ``cryptography`` availability).
    """
    if _HAS_CRYPTOGRAPHY:
        return _encrypt_v3(seed_bytes, passphrase)
    return _encrypt_v2(seed_bytes, passphrase)


def _encrypt_v2(
    seed_bytes: bytes, passphrase: str,
) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_encryption_keys(
        passphrase, salt,
    )
    ciphertext = _xor_bytes(
        seed_bytes,
        _keystream(enc_key, nonce, len(seed_bytes)),
    )

    header = struct.pack(
        _V2_HEADER_FMT,
        ENC_MAGIC, ENC_VERSION,
        len(salt), len(nonce), len(ciphertext),
        SCRYPT_N_DEFAULT, SCRYPT_R_DEFAULT,
        SCRYPT_P_DEFAULT, 0,
    )
    payload = header + salt + nonce + ciphertext
    mac = hmac.new(
        mac_key, payload, hashlib.sha256,
    ).digest()
    return payload + mac


def _encrypt_v3(
    seed_bytes: bytes, passphrase: str,
) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(AEAD_NONCE_LEN)
    aead_key = _derive_aead_key(passphrase, salt)
    ct_len = len(seed_bytes) + AEAD_TAG_LEN

    header = struct.pack(
        _V3_HEADER_FMT,
        ENC_MAGIC, ENC_VERSION_V3,
        ALGO_AES_256_GCM,
        len(salt), AEAD_NONCE_LEN,
        0, 0, 0,
        ct_len,
        SCRYPT_N_DEFAULT, SCRYPT_R_DEFAULT,
        SCRYPT_P_DEFAULT, 0,
    )
    ciphertext_with_tag = _encrypt_aead(
        seed_bytes, aead_key, nonce, aad=header,
    )
    return header + salt + nonce + ciphertext_with_tag


def decrypt_seed_bytes(blob: bytes, passphrase: str) -> bytes:
    """Decrypt an HLE1 envelope back to plaintext.

    Validates the envelope structure, then decrypts
    using the appropriate version path (v1/v2 legacy
    stream cipher or v3 AEAD).

    Args:
        blob: Complete HLE1 envelope bytes.
        passphrase: Passphrase used during
            encryption.

    Returns:
        Decrypted plaintext HLX1 seed bytes.

    Raises:
        SeedFormatError: If authentication fails
            (wrong key or tampered data) or the
            envelope is malformed.
    """
    info = validate_encrypted_seed_envelope(blob)

    if info.version == 3:
        return _decrypt_v3(blob, passphrase, info)
    return _decrypt_v1v2(blob, passphrase, info)


def _decrypt_v1v2(
    blob: bytes,
    passphrase: str,
    info: EncryptedEnvelopeInfo,
) -> bytes:
    salt_off = info.header_len
    nonce_off = salt_off + info.salt_len
    ciphertext_off = nonce_off + info.nonce_len
    salt = blob[salt_off:nonce_off]
    nonce = blob[nonce_off:ciphertext_off]
    ciphertext = blob[
        ciphertext_off : ciphertext_off + info.ciphertext_len
    ]
    mac = blob[-32:]

    enc_key, mac_key = _derive_encryption_keys(
        passphrase, salt,
        n=info.scrypt_n, r=info.scrypt_r, p=info.scrypt_p,
    )
    payload = blob[:-32]
    expected_mac = hmac.new(
        mac_key, payload, hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise SeedFormatError(
            "Encrypted seed authentication failed"
            " (wrong key or tampering).",
            next_action=ACTION_VERIFY_ENCRYPTION,
        )
    return _xor_bytes(
        ciphertext,
        _keystream(enc_key, nonce, len(ciphertext)),
    )


def _decrypt_v3(
    blob: bytes,
    passphrase: str,
    info: EncryptedEnvelopeInfo,
) -> bytes:
    if not _HAS_CRYPTOGRAPHY:
        raise SeedFormatError(
            "HLE1 v3 decryption requires the"
            " cryptography package.",
            next_action=ACTION_INSTALL_CRYPTO,
        )
    if info.algo_id != ALGO_AES_256_GCM:
        raise SeedFormatError(
            "Unsupported AEAD algorithm"
            f" id: {info.algo_id}",
            next_action=ACTION_UPGRADE_HELIX,
        )
    aad = blob[: info.header_len]
    salt_off = info.header_len
    nonce_off = salt_off + info.salt_len
    ct_off = nonce_off + info.nonce_len
    salt = blob[salt_off:nonce_off]
    nonce = blob[nonce_off:ct_off]
    ciphertext_with_tag = blob[
        ct_off : ct_off + info.ciphertext_len
    ]

    aead_key = _derive_aead_key(
        passphrase, salt,
        n=info.scrypt_n, r=info.scrypt_r, p=info.scrypt_p,
    )
    return _decrypt_aead(
        ciphertext_with_tag, aead_key, nonce, aad,
    )


def serialize_seed(
    manifest: dict[str, Any],
    recipe: Recipe,
    raw_payloads: dict[int, bytes],
    manifest_compression: str = "zlib",
    signature_key: str | None = None,
    signature_key_id: str = "default",
) -> bytes:
    """Assemble a complete HLX1 seed binary.

    Builds sections in order: manifest, recipe,
    optional RAW payloads, optional signature, and
    integrity.

    Args:
        manifest: Seed manifest dictionary.
        recipe: Chunk recipe with hash table and ops.
        raw_payloads: Map of hash-table index to
            embedded chunk data.
        manifest_compression: Compression for the
            manifest section.  One of ``"none"``,
            ``"zlib"``, ``"zstd"``.
        signature_key: HMAC key for signing.
            ``None`` skips the signature section.
        signature_key_id: Key identifier stored in
            the signature section.

    Returns:
        Complete HLX1 binary seed bytes.

    Raises:
        SeedFormatError: If ``manifest_compression``
            is not a recognised name.
    """
    if manifest_compression not in _COMPRESSION_NAME_TO_ID:
        raise SeedFormatError(
            "Unsupported manifest compression:"
            f" {manifest_compression}",
            next_action=ACTION_CHECK_OPTIONS,
        )

    manifest_json = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    c_id = _COMPRESSION_NAME_TO_ID[manifest_compression]
    manifest_payload = (
        bytes([c_id])
        + _compress(manifest_json, manifest_compression)
    )
    recipe_payload = encode_recipe(recipe)

    sections: list[tuple[int, bytes]] = [
        (SECTION_MANIFEST, manifest_payload),
        (SECTION_RECIPE, recipe_payload),
    ]
    raw_section_payload: bytes | None = None
    if raw_payloads:
        raw_section_payload = encode_raw_payloads(raw_payloads)
        sections.append((SECTION_RAW, raw_section_payload))

    extra_sections = 1 if signature_key is None else 2
    header = struct.pack(
        ">4sHH", MAGIC, VERSION,
        len(sections) + extra_sections,
    )
    signed_payload = bytearray(header)
    for stype, payload in sections:
        signed_payload.extend(_pack_section(stype, payload))

    payload_without_integrity = bytearray(signed_payload)
    if signature_key is not None:
        signature_payload = _build_signature_payload(
            bytes(signed_payload),
            signature_key=signature_key,
            key_id=signature_key_id,
        )
        payload_without_integrity.extend(
            _pack_section(SECTION_SIGNATURE, signature_payload)
        )

    integrity = {
        "manifest_crc32": zlib.crc32(manifest_payload) & 0xFFFFFFFF,
        "recipe_crc32": zlib.crc32(recipe_payload) & 0xFFFFFFFF,
        "payload_crc32": zlib.crc32(payload_without_integrity) & 0xFFFFFFFF,
        "manifest_sha256": _sha256_hex(manifest_payload),
        "recipe_sha256": _sha256_hex(recipe_payload),
        "payload_sha256": _sha256_hex(payload_without_integrity),
    }
    if raw_section_payload is not None:
        integrity["raw_crc32"] = zlib.crc32(raw_section_payload) & 0xFFFFFFFF
        integrity["raw_sha256"] = _sha256_hex(raw_section_payload)
    integrity_payload = json.dumps(
        integrity, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")

    return bytes(
        payload_without_integrity
        + _pack_section(SECTION_INTEGRITY, integrity_payload)
    )


def _parse_hlx1_header(data: bytes) -> int:
    if len(data) < 8:
        raise SeedFormatError(
            "Seed file too short.",
            next_action=ACTION_REFETCH_SEED,
        )
    magic, version, section_count = struct.unpack_from(
        ">4sHH", data, 0,
    )
    if magic != MAGIC:
        raise SeedFormatError(
            "Invalid seed magic; expected HLX1.",
            next_action=ACTION_VERIFY_SEED,
        )
    if version != VERSION:
        raise SeedFormatError(
            f"Unsupported seed version: {version}",
            next_action=ACTION_UPGRADE_HELIX,
        )
    return int(section_count)


def _scan_hlx1_sections(
    data: bytes, section_count: int,
) -> tuple[dict[int, bytes], dict[int, int]]:
    offset = 8
    payloads: dict[int, bytes] = {}
    section_starts: dict[int, int] = {}

    for _ in range(section_count):
        if offset + 10 > len(data):
            raise SeedFormatError(
                "Section header truncated.",
                next_action=ACTION_REFETCH_SEED,
            )
        section_start = offset
        stype, length = struct.unpack_from(
            ">HQ", data, offset,
        )
        offset += 10
        if offset + length > len(data):
            raise SeedFormatError(
                "Section payload truncated.",
                next_action=ACTION_REFETCH_SEED,
            )
        payloads[stype] = data[offset : offset + length]
        section_starts[stype] = section_start
        offset += length

    if offset != len(data):
        raise SeedFormatError(
            "Seed has trailing bytes outside"
            " sections.",
            next_action=ACTION_REFETCH_SEED,
        )

    return payloads, section_starts


def _check_required_sections(
    payloads: dict[int, bytes],
) -> None:
    if (
        SECTION_MANIFEST not in payloads
        or SECTION_RECIPE not in payloads
        or SECTION_INTEGRITY not in payloads
    ):
        raise SeedFormatError(
            "Seed missing required section(s).",
            next_action=ACTION_REGENERATE_SEED,
        )


def _verify_hlx1_integrity(
    data: bytes,
    payloads: dict[int, bytes],
    section_starts: dict[int, int],
) -> None:
    integrity_payload = payloads[SECTION_INTEGRITY]
    try:
        integrity = json.loads(
            integrity_payload.decode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001
        raise SeedFormatError(
            "Integrity section is not valid JSON.",
            next_action=ACTION_REGENERATE_SEED,
        ) from exc

    integrity_start = section_starts[SECTION_INTEGRITY]
    sig_start = section_starts.get(SECTION_SIGNATURE)
    if (
        sig_start is not None
        and sig_start > integrity_start
    ):
        raise SeedFormatError(
            "Signature section must appear"
            " before integrity section.",
            next_action=ACTION_REGENERATE_SEED,
        )

    manifest_pl = payloads[SECTION_MANIFEST]
    recipe_pl = payloads[SECTION_RECIPE]
    pre_integrity = data[:integrity_start]

    m_crc = zlib.crc32(manifest_pl) & 0xFFFFFFFF
    r_crc = zlib.crc32(recipe_pl) & 0xFFFFFFFF
    p_crc = zlib.crc32(pre_integrity) & 0xFFFFFFFF
    for field, expected, label in [
        ("manifest_crc32", m_crc, "Manifest"),
        ("recipe_crc32", r_crc, "Recipe"),
        ("payload_crc32", p_crc, "Seed payload"),
    ]:
        if integrity.get(field) != expected:
            raise SeedFormatError(
                f"{label} CRC32 mismatch;"
                " seed may be corrupted"
                " or tampered.",
                next_action=ACTION_REFETCH_SEED,
            )

    m_sha = _sha256_hex(manifest_pl)
    r_sha = _sha256_hex(recipe_pl)
    p_sha = _sha256_hex(pre_integrity)
    for field, exp_sha, label in [
        ("manifest_sha256", m_sha, "Manifest"),
        ("recipe_sha256", r_sha, "Recipe"),
        ("payload_sha256", p_sha, "Seed payload"),
    ]:
        if (
            field in integrity
            and integrity[field] != exp_sha
        ):
            raise SeedFormatError(
                f"{label} SHA-256 mismatch;"
                " seed may be corrupted"
                " or tampered.",
                next_action=ACTION_REFETCH_SEED,
            )

    raw_payload = payloads.get(SECTION_RAW)
    if raw_payload is not None:
        raw_crc = zlib.crc32(raw_payload) & 0xFFFFFFFF
        raw_sha = _sha256_hex(raw_payload)
        if (
            "raw_crc32" in integrity
            and integrity["raw_crc32"] != raw_crc
        ):
            raise SeedFormatError(
                "RAW CRC32 mismatch;"
                " seed may be corrupted"
                " or tampered.",
                next_action=ACTION_REFETCH_SEED,
            )
        if (
            "raw_sha256" in integrity
            and integrity["raw_sha256"] != raw_sha
        ):
            raise SeedFormatError(
                "RAW SHA-256 mismatch;"
                " seed may be corrupted"
                " or tampered.",
                next_action=ACTION_REFETCH_SEED,
            )


def _decode_manifest_payload(
    payload: bytes,
) -> tuple[dict[str, Any], str]:
    if not payload:
        raise SeedFormatError(
            "Manifest section empty.",
            next_action=ACTION_REGENERATE_SEED,
        )
    compression_id = payload[0]
    compression_name = _COMPRESSION_ID_TO_NAME.get(
        compression_id,
    )
    if compression_name is None:
        raise SeedFormatError(
            "Unknown manifest compression"
            f" id: {compression_id}",
            next_action=ACTION_REGENERATE_SEED,
        )
    manifest_bytes = _decompress(
        payload[1:], compression_id,
    )
    try:
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001
        raise SeedFormatError(
            "Manifest JSON decode failed.",
            next_action=ACTION_REGENERATE_SEED,
        ) from exc
    return manifest, compression_name


def _decode_signature_section(
    payload: bytes | None,
    section_start: int | None,
    data: bytes,
) -> tuple[dict[str, Any] | None, bytes | None]:
    if payload is None:
        return None, None
    try:
        signature = json.loads(
            payload.decode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001
        raise SeedFormatError(
            "Signature section is not valid JSON.",
            next_action=ACTION_REGENERATE_SEED,
        ) from exc
    if section_start is None:
        raise SeedFormatError(
            "Signature section position"
            " not found.",
            next_action=ACTION_REPORT_BUG,
        )
    return signature, data[:section_start]


def parse_seed(data: bytes) -> Seed:
    """Parse an HLX1 binary seed into its components.

    Validates the header, scans TLV sections,
    verifies CRC32/SHA-256 integrity, and decodes
    the manifest, recipe, raw payloads, and optional
    signature.

    Args:
        data: Complete HLX1 seed bytes (unencrypted).

    Returns:
        Parsed ``Seed`` dataclass.

    Raises:
        SeedFormatError: If the seed is malformed,
            truncated, or integrity checks fail.
    """
    section_count = _parse_hlx1_header(data)
    payloads, section_starts = _scan_hlx1_sections(
        data, section_count,
    )
    _check_required_sections(payloads)
    _verify_hlx1_integrity(
        data, payloads, section_starts,
    )

    manifest, compression_name = (
        _decode_manifest_payload(
            payloads[SECTION_MANIFEST],
        )
    )
    recipe = decode_recipe(payloads[SECTION_RECIPE])
    raw_payloads = (
        decode_raw_payloads(payloads[SECTION_RAW])
        if SECTION_RAW in payloads
        else {}
    )
    signature, signed_payload = (
        _decode_signature_section(
            payloads.get(SECTION_SIGNATURE),
            section_starts.get(SECTION_SIGNATURE),
            data,
        )
    )

    return Seed(
        manifest=manifest,
        recipe=recipe,
        raw_payloads=raw_payloads,
        manifest_compression=compression_name,
        signature=signature,
        signed_payload=signed_payload,
    )


def read_seed(path: str | Path, *, encryption_key: str | None = None) -> Seed:
    """Read and parse a seed file from disk.

    Automatically detects HLE1 encryption and
    decrypts before parsing when an encryption key
    is provided.

    Args:
        path: Path to the ``.hlx`` seed file.
        encryption_key: Passphrase for decryption.
            Required if the seed is encrypted.

    Returns:
        Parsed ``Seed`` dataclass.

    Raises:
        SeedFormatError: If the seed is encrypted
            but no key is provided, or if parsing
            fails.
    """
    blob = Path(path).read_bytes()
    if is_encrypted_seed_data(blob):
        if encryption_key is None:
            raise SeedFormatError(
                "Encrypted seed requires decryption"
                " key. Provide --encryption-key"
                " or set HELIX_ENCRYPTION_KEY.",
                next_action=ACTION_PROVIDE_ENCRYPTION_KEY,
            )
        blob = decrypt_seed_bytes(blob, encryption_key)
    return parse_seed(blob)


def write_seed(
    path: str | Path,
    manifest: dict[str, Any],
    recipe: Recipe,
    raw_payloads: dict[int, bytes],
    manifest_compression: str,
    signature_key: str | None = None,
    signature_key_id: str = "default",
    encryption_key: str | None = None,
) -> None:
    """Serialize and write an HLX1 seed to disk.

    Assembles the seed binary, optionally wraps it
    in HLE1 encryption, and writes to ``path``.

    Args:
        path: Destination file path.
        manifest: Seed manifest dictionary.
        recipe: Chunk recipe with hash table and ops.
        raw_payloads: Map of hash-table index to
            embedded chunk data.
        manifest_compression: Compression algorithm
            name for the manifest section.
        signature_key: HMAC key for signing.
            ``None`` skips the signature.
        signature_key_id: Key identifier stored in
            the signature section.
        encryption_key: Passphrase for HLE1
            encryption.  ``None`` skips encryption.

    Raises:
        SeedFormatError: If ``manifest_compression``
            is unsupported.
    """
    data = serialize_seed(
        manifest=manifest,
        recipe=recipe,
        raw_payloads=raw_payloads,
        manifest_compression=manifest_compression,
        signature_key=signature_key,
        signature_key_id=signature_key_id,
    )
    if encryption_key is not None:
        data = encrypt_seed_bytes(data, encryption_key)
    Path(path).write_bytes(data)


def sign_seed_file(
    in_path: str | Path,
    out_path: str | Path,
    *,
    signature_key: str,
    signature_key_id: str = "default",
) -> None:
    """Add an HMAC-SHA256 signature to a seed file.

    Reads the seed from ``in_path``, re-serializes
    it with the signature, and writes the result to
    ``out_path``.

    Args:
        in_path: Path to the unsigned seed file.
        out_path: Destination path for the signed
            seed.
        signature_key: HMAC key used for signing.
        signature_key_id: Key identifier stored in
            the signature section.
    """
    seed = read_seed(in_path)
    write_seed(
        path=out_path,
        manifest=seed.manifest,
        recipe=seed.recipe,
        raw_payloads=seed.raw_payloads,
        manifest_compression=seed.manifest_compression,
        signature_key=signature_key,
        signature_key_id=signature_key_id,
    )


def verify_signature(
    seed: Seed, signature_key: str,
) -> tuple[bool, str | None]:
    """Verify the HMAC-SHA256 signature of a seed.

    Checks the algorithm, payload hash, and HMAC
    value against the provided key.

    Args:
        seed: Parsed seed with optional signature.
        signature_key: HMAC key to verify against.

    Returns:
        Tuple of ``(True, None)`` on success, or
        ``(False, reason)`` describing the failure.
    """
    if seed.signature is None:
        return False, "Signature is missing."
    if seed.signed_payload is None:
        return False, "Signed payload is unavailable."

    algorithm = seed.signature.get("algorithm")
    if algorithm != "hmac-sha256":
        return False, f"Unsupported signature algorithm: {algorithm}"

    expected_payload_sha = _sha256_hex(seed.signed_payload)
    if seed.signature.get("signed_payload_sha256") != expected_payload_sha:
        return False, "Signature payload hash mismatch."

    expected_signature = _hmac_sha256_hex(seed.signed_payload, signature_key)
    provided_signature = seed.signature.get("signature")
    if not isinstance(provided_signature, str):
        return False, "Signature value is missing."
    if not hmac.compare_digest(provided_signature, expected_signature):
        return False, "Signature verification failed."

    return True, None
