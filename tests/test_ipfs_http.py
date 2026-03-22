"""Unit tests for kubo HTTP RPC client (monkeypatch, no daemon)."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from seedbraid import ipfs_http
from seedbraid.errors import ExternalToolError


class _FakeResponse:
    """Minimal urllib response mock."""

    def __init__(
        self,
        data: bytes,
        status: int = 200,
    ) -> None:
        self._data = data
        self.status = status

    def read(self) -> bytes:
        return self._data

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *_: object) -> None:
        pass


# -- api_base_url -----------------------------------------------


def test_api_base_url_default(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    assert ipfs_http.api_base_url() == (
        "http://127.0.0.1:5001/api/v0"
    )


def test_api_base_url_from_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "SB_KUBO_API", "http://localhost:9001/api/v0"
    )
    assert ipfs_http.api_base_url() == (
        "http://localhost:9001/api/v0"
    )


def test_api_base_url_strips_trailing_slash(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SB_KUBO_API", "http://127.0.0.1:5001/api/v0/"
    )
    assert ipfs_http.api_base_url().endswith("/v0")


# -- post_json ---------------------------------------------------


def test_post_json_success(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen",
        lambda req, **kw: _FakeResponse(
            json.dumps({"Hash": "QmTest"}).encode(),
        ),
    )
    result = ipfs_http.post_json("/add", quiet="true")
    assert result == {"Hash": "QmTest"}


def test_post_json_connection_error(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)

    def _raise(*_a, **_kw):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _raise
    )
    with pytest.raises(ExternalToolError) as exc_info:
        ipfs_http.post_json("/version")
    assert exc_info.value.code == "SB_E_KUBO_API_UNREACHABLE"


def test_post_json_http_error_with_message(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    body = json.dumps({"Message": "pin not found"}).encode()

    def _raise(*_a, **_kw):
        raise urllib.error.HTTPError(
            "http://localhost:5001/api/v0/pin/ls",
            500,
            "Internal Server Error",
            {},  # type: ignore[arg-type]
            io.BytesIO(body),
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _raise
    )
    with pytest.raises(ExternalToolError) as exc_info:
        ipfs_http.post_json("/pin/ls", arg="QmBad")
    assert "pin not found" in str(exc_info.value)
    assert exc_info.value.code == "SB_E_KUBO_API_ERROR"


def test_post_json_query_params(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    captured: list[object] = []

    def _capture(req, **kw):  # noqa: ANN001, ANN003
        captured.append(req)
        return _FakeResponse(b'{"ok":true}')

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _capture
    )
    ipfs_http.post_json("/pin/add", arg="QmAbc")
    url = captured[0].full_url  # type: ignore[union-attr]
    assert "arg=QmAbc" in url


# -- post_raw ----------------------------------------------------


def test_post_raw_returns_bytes(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen",
        lambda req, **kw: _FakeResponse(b"\x00\x01\x02"),
    )
    assert ipfs_http.post_raw("/cat", arg="QmX") == (
        b"\x00\x01\x02"
    )


def test_post_raw_connection_error(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)

    def _raise(*_a, **_kw):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _raise
    )
    with pytest.raises(ExternalToolError):
        ipfs_http.post_raw("/cat", arg="QmX")


# -- post_multipart_json -----------------------------------------


def test_post_multipart_json_success(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    captured: list[object] = []

    def _capture(req, **kw):  # noqa: ANN001, ANN003
        captured.append(req)
        return _FakeResponse(
            json.dumps({"Key": "QmNew"}).encode(),
        )

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _capture
    )
    result = ipfs_http.post_multipart_json(
        "/block/put", "data", b"chunk-bytes"
    )
    assert result == {"Key": "QmNew"}
    req = captured[0]
    ct = req.get_header("Content-type")  # type: ignore[union-attr]
    assert ct.startswith("multipart/form-data; boundary=")


def test_post_multipart_json_with_params(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    captured: list[object] = []

    def _capture(req, **kw):  # noqa: ANN001, ANN003
        captured.append(req)
        return _FakeResponse(b'{"ok":true}')

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _capture
    )
    ipfs_http.post_multipart_json(
        "/block/put",
        "data",
        b"x",
        **{"cid-codec": "raw", "mhtype": "sha2-256"},
    )
    url = captured[0].full_url  # type: ignore[union-attr]
    assert "cid-codec=raw" in url
    assert "mhtype=sha2-256" in url


# -- post_void ---------------------------------------------------


def test_post_void_success(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen",
        lambda req, **kw: _FakeResponse(b""),
    )
    ipfs_http.post_void("/files/mkdir", arg="/chunks")


def test_post_void_error(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)

    def _raise(*_a, **_kw):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _raise
    )
    with pytest.raises(ExternalToolError):
        ipfs_http.post_void("/files/mkdir", arg="/x")


# -- check_daemon ------------------------------------------------


def test_check_daemon_true(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen",
        lambda req, **kw: _FakeResponse(
            json.dumps({"Version": "0.28.0"}).encode(),
        ),
    )
    assert ipfs_http.check_daemon() is True


def test_check_daemon_false(monkeypatch) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)

    def _raise(*_a, **_kw):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _raise
    )
    assert ipfs_http.check_daemon() is False


# -- multi-arg ---------------------------------------------------


def test_post_json_multiple_arg_params(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SB_KUBO_API", raising=False)
    captured: list[object] = []

    def _capture(req, **kw):  # noqa: ANN001, ANN003
        captured.append(req)
        return _FakeResponse(b'{"ok":true}')

    monkeypatch.setattr(
        "seedbraid.ipfs_http.urlopen", _capture
    )
    ipfs_http.post_json(
        "/files/cp",
        arg=["/ipfs/QmSrc", "/chunks/dst"],
    )
    url = captured[0].full_url  # type: ignore[union-attr]
    assert "arg=%2Fipfs%2FQmSrc" in url
    assert "arg=%2Fchunks%2Fdst" in url
