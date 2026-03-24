"""kubo HTTP RPC client (thin wrapper over urllib).

All IPFS operations in seedbraid route through this module.
The API endpoint defaults to ``http://127.0.0.1:5001/api/v0``
and is overridable via the ``SB_KUBO_API`` environment variable.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from urllib.request import Request, urlopen

from .errors import ACTION_CHECK_KUBO_API, ExternalToolError

if TYPE_CHECKING:
    from typing import BinaryIO

_DEFAULT_API = "http://127.0.0.1:5001/api/v0"
_DEFAULT_TIMEOUT = 30


def api_base_url() -> str:
    """Return kubo API base URL from SB_KUBO_API or default."""
    url = os.environ.get("SB_KUBO_API", _DEFAULT_API)
    return url.rstrip("/")


def _timeout() -> int:
    """Return request timeout from SB_KUBO_TIMEOUT or default."""
    return int(
        os.environ.get("SB_KUBO_TIMEOUT", _DEFAULT_TIMEOUT)
    )


def _build_url(
    path: str,
    **params: str | list[str],
) -> str:
    """Build full URL with query parameters.

    List values are expanded as repeated keys:
    ``arg=["a","b"]`` becomes ``arg=a&arg=b``.
    """
    base = api_base_url() + path
    if not params:
        return base
    pairs: list[tuple[str, str]] = []
    for key, val in params.items():
        if isinstance(val, list):
            for v in val:
                pairs.append((key, v))
        else:
            pairs.append((key, val))
    return base + "?" + urllib.parse.urlencode(pairs)


def _handle_error(exc: Exception) -> NoReturn:
    """Convert urllib errors to ExternalToolError."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = json.loads(exc.read().decode())
            msg = body.get("Message", str(exc))
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            OSError,
        ):
            msg = str(exc)
        raise ExternalToolError(
            msg,
            code="SB_E_KUBO_API_ERROR",
            next_action=ACTION_CHECK_KUBO_API,
        ) from exc
    raise ExternalToolError(
        f"Cannot reach kubo API: {exc}",
        code="SB_E_KUBO_API_UNREACHABLE",
        next_action=ACTION_CHECK_KUBO_API,
    ) from exc


def _execute(req: Request) -> bytes:
    """Send request, return raw response bytes."""
    try:
        with urlopen(req, timeout=_timeout()) as resp:
            data: bytes = resp.read()
            return data
    except urllib.error.URLError as exc:
        _handle_error(exc)


def post_json(
    path: str,
    **params: str | list[str],
) -> dict:
    """POST to kubo API, parse JSON response."""
    req = Request(_build_url(path, **params), method="POST")
    result: dict = json.loads(_execute(req))
    return result


def post_raw(
    path: str,
    **params: str | list[str],
) -> bytes:
    """POST to kubo API, return raw bytes."""
    req = Request(_build_url(path, **params), method="POST")
    return _execute(req)


def _multipart_body(
    field_name: str,
    data: bytes,
    filename: str,
    boundary: str,
) -> bytes:
    """Build multipart/form-data body."""
    header = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data;"
        f' name="{field_name}";'
        f' filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream"
        f"\r\n\r\n"
    ).encode()
    footer = f"\r\n--{boundary}--\r\n".encode()
    return b"".join((header, data, footer))


def post_multipart_json(
    path: str,
    field_name: str,
    data: bytes | BinaryIO,
    filename: str = "data",
    **params: str | list[str],
) -> dict:
    """POST multipart/form-data, parse JSON response."""
    boundary = uuid.uuid4().hex
    raw = data if isinstance(data, bytes) else data.read()
    body = _multipart_body(
        field_name, raw, filename, boundary
    )
    req = Request(
        _build_url(path, **params),
        data=body,
        method="POST",
        headers={
            "Content-Type": (
                "multipart/form-data;"
                f" boundary={boundary}"
            ),
        },
    )
    result: dict = json.loads(_execute(req))
    return result


def post_multipart_file_json(
    path: str,
    file_path: Path,
    **params: str | list[str],
) -> dict:
    """POST file as multipart/form-data, parse JSON response.

    Delegates to :func:`post_multipart_json`. Seed files are
    typically small (~KB), so full read is acceptable.
    """
    return post_multipart_json(
        path,
        "file",
        file_path.read_bytes(),
        filename=file_path.name,
        **params,
    )


def post_void(
    path: str,
    **params: str | list[str],
) -> None:
    """POST to kubo API, discard response body."""
    req = Request(_build_url(path, **params), method="POST")
    _execute(req)  # drain socket, discard bytes


def check_daemon() -> bool:
    """Return True if kubo daemon responds to /api/v0/version."""
    try:
        post_json("/version")
    except ExternalToolError:
        return False
    return True


def daemon_version() -> str | None:
    """Return kubo version string, or None if unreachable."""
    try:
        resp = post_json("/version")
    except ExternalToolError:
        return None
    return resp.get("Version")
