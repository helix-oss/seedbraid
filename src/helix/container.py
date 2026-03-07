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
    out = bytearray(struct.pack(">I", len(raw_payloads)))
    for index in sorted(raw_payloads):
        payload = raw_payloads[index]
        out.extend(struct.pack(">II", index, len(payload)))
        out.extend(payload)
    return bytes(out)


def decode_raw_payloads(data: bytes) -> dict[int, bytes]:
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


def _derive_encryption_keys(
    passphrase: str,
    salt: bytes,
    *,
    n: int = SCRYPT_N_DEFAULT,
    r: int = SCRYPT_R_DEFAULT,
    p: int = SCRYPT_P_DEFAULT,
) -> tuple[bytes, bytes]:
    base_key = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=32,
        maxmem=256 * r * n + 1024 * 1024,
    )
    enc_key = hashlib.sha256(base_key + b"enc").digest()
    mac_key = hashlib.sha256(base_key + b"mac").digest()
    return enc_key, mac_key


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


def validate_encrypted_seed_envelope(
    blob: bytes,
) -> EncryptedEnvelopeInfo:
    if len(blob) < 4 + 2 + 1 + 1 + 8 + 32:
        raise SeedFormatError(
            "Encrypted seed is too short.",
            next_action=ACTION_REFETCH_SEED,
        )
    (
        magic, version, salt_len, nonce_len, ciphertext_len,
    ) = struct.unpack_from(">4sHBBQ", blob, 0)
    if magic != ENC_MAGIC:
        raise SeedFormatError(
            "Encrypted seed magic mismatch."
            " Expected HLE1.",
            next_action=ACTION_REFETCH_SEED,
        )

    if version == 1:
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
            scrypt_n, scrypt_r, scrypt_p, reserved,
        ) = struct.unpack_from(">IBBH", blob, 16)
        if scrypt_n < SCRYPT_N_MIN:
            raise SeedFormatError(
                f"scrypt n={scrypt_n} below"
                f" minimum {SCRYPT_N_MIN};"
                " possible downgrade attack.",
                next_action=ACTION_REFETCH_SEED,
            )
        if reserved != 0:
            raise SeedFormatError(
                "Reserved field in encrypted"
                " seed header is non-zero.",
                next_action=ACTION_UPGRADE_HELIX,
            )
        header_len = 24
    else:
        raise SeedFormatError(
            "Unsupported encrypted seed"
            f" version: {version}",
            next_action=ACTION_UPGRADE_HELIX,
        )

    payload_len = (
        header_len + salt_len + nonce_len + ciphertext_len
    )
    if len(blob) != payload_len + 32:
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
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_encryption_keys(passphrase, salt)
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
    mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
    return payload + mac


def decrypt_seed_bytes(blob: bytes, passphrase: str) -> bytes:
    info = validate_encrypted_seed_envelope(blob)

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


def serialize_seed(
    manifest: dict[str, Any],
    recipe: Recipe,
    raw_payloads: dict[int, bytes],
    manifest_compression: str = "zlib",
    signature_key: str | None = None,
    signature_key_id: str = "default",
) -> bytes:
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
