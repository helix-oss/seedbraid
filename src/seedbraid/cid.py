"""CIDv1 (raw codec) computation from SHA-256 digests.

Implements multibase/multihash/CID encoding using only
the Python standard library.

CIDv1 raw codec structure (36 bytes)::

  0x01          -- version 1
  0x55          -- raw codec
  0x12          -- sha2-256 multihash function code
  0x20          -- multihash digest length (32)
  <32 bytes>    -- SHA-256 digest

Encoded as base32-lower with ``b`` multibase prefix,
matching the output of ``ipfs block put --cid-codec raw``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib

# CID version 1
_CID_VERSION: int = 0x01
# Multicodec: raw binary (no codec wrapping)
_CODEC_RAW: int = 0x55
# Multihash function code: sha2-256
_MHASH_SHA256: int = 0x12
# SHA-256 digest length in bytes
_DIGEST_LEN: int = 0x20
# Fixed 4-byte CID prefix for raw+sha256
_CID_PREFIX: bytes = bytes([
    _CID_VERSION,
    _CODEC_RAW,
    _MHASH_SHA256,
    _DIGEST_LEN,
])
# Total CID binary length: prefix (4) + digest (32)
_CID_BINARY_LEN: int = len(_CID_PREFIX) + _DIGEST_LEN


def sha256_to_cidv1_raw(
    data_or_digest: bytes,
    *,
    is_digest: bool = False,
) -> str:
    """Compute CIDv1 raw codec CID from data or digest.

    When *is_digest* is ``False``, computes SHA-256 of
    *data_or_digest* first.  When ``True``, treats the
    input as a pre-computed 32-byte SHA-256 digest.

    Args:
        data_or_digest: Raw data bytes or 32-byte
            SHA-256 digest.
        is_digest: If ``True``, skip SHA-256 hashing.

    Returns:
        Base32-lower CIDv1 string (``b`` prefix).

    Raises:
        ValueError: If *is_digest* is ``True`` and
            length is not 32 bytes.
    """
    if is_digest:
        if len(data_or_digest) != _DIGEST_LEN:
            msg = (
                "Expected 32-byte SHA-256 digest, "
                f"got {len(data_or_digest)}"
            )
            raise ValueError(msg)
        digest = data_or_digest
    else:
        digest = hashlib.sha256(data_or_digest).digest()

    cid_bytes = _CID_PREFIX + digest
    encoded = (
        base64.b32encode(cid_bytes)
        .decode("ascii")
        .lower()
        .rstrip("=")
    )
    return "b" + encoded


def cidv1_raw_to_sha256(cid: str) -> bytes:
    """Extract 32-byte SHA-256 digest from CIDv1 raw.

    Args:
        cid: Base32-lower CIDv1 string.

    Returns:
        32-byte SHA-256 digest.

    Raises:
        ValueError: If CID is not a valid CIDv1 raw
            codec with sha2-256 multihash.
    """
    if not cid.startswith("b"):
        msg = (
            "Not a base32-lower CIDv1 "
            f"(expected 'b' prefix): {cid!r}"
        )
        raise ValueError(msg)

    body = cid[1:].upper()
    pad = (8 - len(body) % 8) % 8
    padded = body + "=" * pad

    try:
        cid_bytes = base64.b32decode(padded)
    except binascii.Error as exc:
        msg = f"Invalid base32 in CID: {cid!r}"
        raise ValueError(msg) from exc

    if len(cid_bytes) != _CID_BINARY_LEN:
        msg = (
            f"Expected {_CID_BINARY_LEN}-byte "
            f"CIDv1 raw, got {len(cid_bytes)}"
        )
        raise ValueError(msg)
    if cid_bytes[0] != _CID_VERSION:
        msg = (
            "Not CIDv1 "
            f"(version byte={cid_bytes[0]:#x})"
        )
        raise ValueError(msg)
    if cid_bytes[1] != _CODEC_RAW:
        msg = (
            "Not raw codec "
            f"(codec byte={cid_bytes[1]:#x})"
        )
        raise ValueError(msg)
    if cid_bytes[2] != _MHASH_SHA256:
        msg = (
            "Not sha2-256 multihash "
            f"(func byte={cid_bytes[2]:#x})"
        )
        raise ValueError(msg)
    if cid_bytes[3] != _DIGEST_LEN:
        msg = (
            "Unexpected multihash length byte: "
            f"{cid_bytes[3]:#x}"
        )
        raise ValueError(msg)

    return cid_bytes[4:]
