from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .errors import SeedFormatError

MAGIC = b"HLX1"
VERSION = 1
ENC_MAGIC = b"HLE1"
ENC_VERSION = 1

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
    manifest: dict
    recipe: Recipe
    raw_payloads: dict[int, bytes]
    manifest_compression: str
    signature: dict | None
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
                "Compression 'zstd' requires optional dependency 'zstandard'."
            ) from exc
        return zstd.ZstdCompressor(level=3).compress(data)
    raise SeedFormatError(f"Unsupported compression: {name}")


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
                "Seed uses zstd compression but 'zstandard' is not installed."
            ) from exc
        return zstd.ZstdDecompressor().decompress(data)
    raise SeedFormatError(f"Unknown manifest compression id: {ctype}")


def encode_recipe(recipe: Recipe) -> bytes:
    out = bytearray()
    out.extend(struct.pack(">II", len(recipe.ops), len(recipe.hash_table)))
    for digest in recipe.hash_table:
        if len(digest) != 32:
            raise SeedFormatError(
                "Recipe hash table must contain"
                " 32-byte SHA-256 digests."
            )
        out.extend(digest)
    for op in recipe.ops:
        out.extend(struct.pack(">BI", op.opcode, op.hash_index))
    return bytes(out)


def decode_recipe(data: bytes) -> Recipe:
    if len(data) < 8:
        raise SeedFormatError("Recipe section too short.")
    op_count, hash_count = struct.unpack_from(">II", data, 0)
    offset = 8
    hash_table: list[bytes] = []
    for _ in range(hash_count):
        if offset + 32 > len(data):
            raise SeedFormatError("Recipe hash table truncated.")
        hash_table.append(data[offset : offset + 32])
        offset += 32

    ops: list[RecipeOp] = []
    for _ in range(op_count):
        if offset + 5 > len(data):
            raise SeedFormatError("Recipe op stream truncated.")
        opcode, index = struct.unpack_from(">BI", data, offset)
        offset += 5
        if opcode not in (OP_REF, OP_RAW):
            raise SeedFormatError(f"Unknown recipe opcode: {opcode}")
        if index >= hash_count:
            raise SeedFormatError("Recipe op hash index out of bounds.")
        ops.append(RecipeOp(opcode=opcode, hash_index=index))

    if offset != len(data):
        raise SeedFormatError("Recipe section has trailing bytes.")
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
        raise SeedFormatError("RAW section too short.")
    count = struct.unpack_from(">I", data, 0)[0]
    offset = 4
    raw: dict[int, bytes] = {}
    for _ in range(count):
        if offset + 8 > len(data):
            raise SeedFormatError("RAW section entry header truncated.")
        index, size = struct.unpack_from(">II", data, offset)
        offset += 8
        if offset + size > len(data):
            raise SeedFormatError("RAW section entry payload truncated.")
        raw[index] = data[offset : offset + size]
        offset += size
    if offset != len(data):
        raise SeedFormatError("RAW section has trailing bytes.")
    return raw


def _pack_section(stype: int, payload: bytes) -> bytes:
    return struct.pack(">HQ", stype, len(payload)) + payload


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256_hex(data: bytes, key: str) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _derive_encryption_keys(
    passphrase: str, salt: bytes,
) -> tuple[bytes, bytes]:
    base_key = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
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


def validate_encrypted_seed_envelope(blob: bytes) -> tuple[int, int, int, int]:
    if len(blob) < 4 + 2 + 1 + 1 + 8 + 32:
        raise SeedFormatError("Encrypted seed is too short.")
    (
        magic, version, salt_len, nonce_len, ciphertext_len,
    ) = struct.unpack_from(">4sHBBQ", blob, 0)
    if magic != ENC_MAGIC:
        raise SeedFormatError("Encrypted seed magic mismatch. Expected HLE1.")
    if version != ENC_VERSION:
        raise SeedFormatError(f"Unsupported encrypted seed version: {version}")

    header_len = 16
    payload_len = header_len + salt_len + nonce_len + ciphertext_len
    if len(blob) != payload_len + 32:
        raise SeedFormatError(
            "Encrypted seed length mismatch"
            " or truncation detected."
        )
    return header_len, salt_len, nonce_len, ciphertext_len


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
        ">4sHBBQ",
        ENC_MAGIC, ENC_VERSION,
        len(salt), len(nonce), len(ciphertext),
    )
    payload = header + salt + nonce + ciphertext
    mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
    return payload + mac


def decrypt_seed_bytes(blob: bytes, passphrase: str) -> bytes:
    (
        header_len, salt_len, nonce_len, ciphertext_len,
    ) = validate_encrypted_seed_envelope(blob)

    salt_off = header_len
    nonce_off = salt_off + salt_len
    ciphertext_off = nonce_off + nonce_len
    salt = blob[salt_off:nonce_off]
    nonce = blob[nonce_off:ciphertext_off]
    ciphertext = blob[ciphertext_off : ciphertext_off + ciphertext_len]
    mac = blob[-32:]

    enc_key, mac_key = _derive_encryption_keys(passphrase, salt)
    payload = blob[:-32]
    expected_mac = hmac.new(mac_key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise SeedFormatError(
            "Encrypted seed authentication failed"
            " (wrong key or tampering)."
        )
    return _xor_bytes(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))


def serialize_seed(
    manifest: dict,
    recipe: Recipe,
    raw_payloads: dict[int, bytes],
    manifest_compression: str = "zlib",
    signature_key: str | None = None,
    signature_key_id: str = "default",
) -> bytes:
    if manifest_compression not in _COMPRESSION_NAME_TO_ID:
        raise SeedFormatError(
            "Unsupported manifest compression:"
            f" {manifest_compression}"
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


def parse_seed(data: bytes) -> Seed:
    if len(data) < 8:
        raise SeedFormatError("Seed file too short.")

    magic, version, section_count = struct.unpack_from(">4sHH", data, 0)
    if magic != MAGIC:
        raise SeedFormatError("Invalid seed magic; expected HLX1.")
    if version != VERSION:
        raise SeedFormatError(f"Unsupported seed version: {version}")

    offset = 8
    manifest_payload = None
    recipe_payload = None
    raw_payload = None
    signature_payload = None
    integrity_payload = None
    signature_section_start = None
    integrity_section_start = None

    for _ in range(section_count):
        if offset + 10 > len(data):
            raise SeedFormatError("Section header truncated.")
        stype, length = struct.unpack_from(">HQ", data, offset)
        offset += 10
        if offset + length > len(data):
            raise SeedFormatError("Section payload truncated.")
        payload = data[offset : offset + length]
        section_start = offset - 10
        offset += length

        if stype == SECTION_MANIFEST:
            manifest_payload = payload
        elif stype == SECTION_RECIPE:
            recipe_payload = payload
        elif stype == SECTION_RAW:
            raw_payload = payload
        elif stype == SECTION_SIGNATURE:
            signature_payload = payload
            signature_section_start = section_start
        elif stype == SECTION_INTEGRITY:
            integrity_payload = payload
            integrity_section_start = section_start

    if offset != len(data):
        raise SeedFormatError("Seed has trailing bytes outside sections.")

    if (
        manifest_payload is None
        or recipe_payload is None
        or integrity_payload is None
    ):
        raise SeedFormatError("Seed missing required section(s).")

    try:
        integrity = json.loads(integrity_payload.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SeedFormatError("Integrity section is not valid JSON.") from exc

    if integrity_section_start is None:
        raise SeedFormatError("Integrity section position not found.")
    if (
        signature_section_start is not None
        and signature_section_start > integrity_section_start
    ):
        raise SeedFormatError(
            "Signature section must appear"
            " before integrity section."
        )

    expected_manifest_crc = zlib.crc32(manifest_payload) & 0xFFFFFFFF
    expected_recipe_crc = zlib.crc32(recipe_payload) & 0xFFFFFFFF
    expected_payload_crc = (
        zlib.crc32(data[:integrity_section_start]) & 0xFFFFFFFF
    )
    expected_manifest_sha256 = _sha256_hex(manifest_payload)
    expected_recipe_sha256 = _sha256_hex(recipe_payload)
    expected_payload_sha256 = _sha256_hex(
        data[:integrity_section_start]
    )

    if integrity.get("manifest_crc32") != expected_manifest_crc:
        raise SeedFormatError(
            "Manifest CRC32 mismatch;"
            " seed may be corrupted or tampered."
        )
    if integrity.get("recipe_crc32") != expected_recipe_crc:
        raise SeedFormatError(
            "Recipe CRC32 mismatch;"
            " seed may be corrupted or tampered."
        )
    if integrity.get("payload_crc32") != expected_payload_crc:
        raise SeedFormatError(
            "Seed payload CRC32 mismatch;"
            " seed may be corrupted or tampered."
        )
    if (
        "manifest_sha256" in integrity
        and integrity["manifest_sha256"]
        != expected_manifest_sha256
    ):
        raise SeedFormatError(
            "Manifest SHA-256 mismatch;"
            " seed may be corrupted or tampered."
        )
    if (
        "recipe_sha256" in integrity
        and integrity["recipe_sha256"]
        != expected_recipe_sha256
    ):
        raise SeedFormatError(
            "Recipe SHA-256 mismatch;"
            " seed may be corrupted or tampered."
        )
    if (
        "payload_sha256" in integrity
        and integrity["payload_sha256"]
        != expected_payload_sha256
    ):
        raise SeedFormatError(
            "Seed payload SHA-256 mismatch;"
            " seed may be corrupted or tampered."
        )
    if raw_payload is not None:
        expected_raw_crc = zlib.crc32(raw_payload) & 0xFFFFFFFF
        expected_raw_sha256 = _sha256_hex(raw_payload)
        if (
            "raw_crc32" in integrity
            and integrity["raw_crc32"] != expected_raw_crc
        ):
            raise SeedFormatError(
                "RAW CRC32 mismatch;"
                " seed may be corrupted or tampered."
            )
        if (
            "raw_sha256" in integrity
            and integrity["raw_sha256"]
            != expected_raw_sha256
        ):
            raise SeedFormatError(
                "RAW SHA-256 mismatch;"
                " seed may be corrupted or tampered."
            )

    if not manifest_payload:
        raise SeedFormatError("Manifest section empty.")
    compression_id = manifest_payload[0]
    manifest_name = _COMPRESSION_ID_TO_NAME.get(compression_id)
    if manifest_name is None:
        raise SeedFormatError(
            "Unknown manifest compression"
            f" id: {compression_id}"
        )

    manifest_bytes = _decompress(manifest_payload[1:], compression_id)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SeedFormatError("Manifest JSON decode failed.") from exc

    recipe = decode_recipe(recipe_payload)
    raw_payloads = (
        decode_raw_payloads(raw_payload)
        if raw_payload is not None
        else {}
    )
    signature = None
    signed_payload = None
    if signature_payload is not None:
        try:
            signature = json.loads(signature_payload.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise SeedFormatError(
                "Signature section is not valid JSON."
            ) from exc
        if signature_section_start is None:
            raise SeedFormatError("Signature section position not found.")
        signed_payload = data[:signature_section_start]

    return Seed(
        manifest=manifest,
        recipe=recipe,
        raw_payloads=raw_payloads,
        manifest_compression=manifest_name,
        signature=signature,
        signed_payload=signed_payload,
    )


def read_seed(path: str | Path, *, encryption_key: str | None = None) -> Seed:
    blob = Path(path).read_bytes()
    if is_encrypted_seed_data(blob):
        if encryption_key is None:
            raise SeedFormatError(
                "Encrypted seed requires decryption key. "
                "Provide --encryption-key or set HELIX_ENCRYPTION_KEY."
            )
        blob = decrypt_seed_bytes(blob, encryption_key)
    return parse_seed(blob)


def write_seed(
    path: str | Path,
    manifest: dict,
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
