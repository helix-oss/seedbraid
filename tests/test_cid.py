"""Unit tests for CIDv1 raw codec computation."""

from __future__ import annotations

import base64
import hashlib

import pytest

from seedbraid.cid import (
    cidv1_raw_to_sha256,
    sha256_to_cidv1_raw,
)


def _compute_expected_cid(data: bytes) -> str:
    """Independent CID computation for cross-check."""
    digest = hashlib.sha256(data).digest()
    cid_bytes = bytes([0x01, 0x55, 0x12, 0x20]) + digest
    encoded = (
        base64.b32encode(cid_bytes)
        .decode("ascii")
        .lower()
        .rstrip("=")
    )
    return "b" + encoded


# -- Known-value tests --


_EMPTY_CID = (
    "bafkreihdwdcefgh4dqkjv67uzcmw7oj"
    "ee6xedzdetojuzjevtenxquvyku"
)
_HELLO_WORLD_CID = (
    "bafkreifzjut3te2nhyekklss27nh3k7"
    "2ysco7y32koao5eei66wof36n5e"
)


def test_empty_bytes_known_cid() -> None:
    cid = sha256_to_cidv1_raw(b"")
    assert cid == _EMPTY_CID
    assert cid == _compute_expected_cid(b"")


def test_hello_world_known_cid() -> None:
    cid = sha256_to_cidv1_raw(b"hello world")
    assert cid == _HELLO_WORLD_CID
    assert cid == _compute_expected_cid(b"hello world")


# -- Format tests --


def test_cid_starts_with_bafkrei() -> None:
    for data in [b"", b"x", b"hello world"]:
        cid = sha256_to_cidv1_raw(data)
        assert cid.startswith("bafkrei"), cid


def test_cid_is_lowercase_no_padding() -> None:
    cid = sha256_to_cidv1_raw(b"test data")
    body = cid[1:]  # skip "b" prefix
    assert body == body.lower()
    assert "=" not in body


# -- Round-trip tests --


def test_roundtrip_data() -> None:
    for data in [b"", b"a", b"hello world", b"\x00" * 64]:
        cid = sha256_to_cidv1_raw(data)
        recovered = cidv1_raw_to_sha256(cid)
        expected = hashlib.sha256(data).digest()
        assert recovered == expected


def test_roundtrip_is_digest_true() -> None:
    digest = hashlib.sha256(b"roundtrip test").digest()
    cid = sha256_to_cidv1_raw(digest, is_digest=True)
    recovered = cidv1_raw_to_sha256(cid)
    assert recovered == digest


def test_is_digest_true_matches_data_mode() -> None:
    data = b"consistency check"
    cid_from_data = sha256_to_cidv1_raw(data)
    digest = hashlib.sha256(data).digest()
    cid_from_digest = sha256_to_cidv1_raw(
        digest, is_digest=True
    )
    assert cid_from_data == cid_from_digest


# -- Error tests --


def test_invalid_digest_length_31_raises() -> None:
    with pytest.raises(ValueError, match="32"):
        sha256_to_cidv1_raw(
            b"\x00" * 31, is_digest=True
        )


def test_invalid_digest_length_33_raises() -> None:
    with pytest.raises(ValueError, match="32"):
        sha256_to_cidv1_raw(
            b"\x00" * 33, is_digest=True
        )


def test_invalid_cid_no_b_prefix() -> None:
    with pytest.raises(ValueError, match="prefix"):
        cidv1_raw_to_sha256("Qm" + "a" * 44)


def test_invalid_cid_wrong_version() -> None:
    digest = hashlib.sha256(b"test").digest()
    bad = bytes([0x02, 0x55, 0x12, 0x20]) + digest
    encoded = (
        base64.b32encode(bad)
        .decode("ascii")
        .lower()
        .rstrip("=")
    )
    bad_cid = "b" + encoded
    with pytest.raises(ValueError, match="CIDv1"):
        cidv1_raw_to_sha256(bad_cid)


def test_invalid_cid_wrong_codec() -> None:
    digest = hashlib.sha256(b"test").digest()
    bad = bytes([0x01, 0x70, 0x12, 0x20]) + digest
    encoded = (
        base64.b32encode(bad)
        .decode("ascii")
        .lower()
        .rstrip("=")
    )
    bad_cid = "b" + encoded
    with pytest.raises(ValueError, match="raw codec"):
        cidv1_raw_to_sha256(bad_cid)


def test_invalid_cid_bad_base32() -> None:
    with pytest.raises(ValueError, match="base32"):
        cidv1_raw_to_sha256("b!!invalid!!")


# -- Determinism tests --


def test_different_data_different_cid() -> None:
    assert sha256_to_cidv1_raw(b"a") != (
        sha256_to_cidv1_raw(b"b")
    )


def test_same_data_same_cid() -> None:
    cid1 = sha256_to_cidv1_raw(b"test")
    cid2 = sha256_to_cidv1_raw(b"test")
    assert cid1 == cid2
