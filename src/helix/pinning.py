from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .errors import ExternalToolError


@dataclass(frozen=True)
class RemotePinResult:
    provider: str
    cid: str
    status: str
    request_id: str | None = None


class RemotePinProvider(Protocol):
    provider_name: str

    def remote_add(
        self,
        cid: str,
        *,
        name: str | None = None,
        timeout_ms: int = 10_000,
        retries: int = 3,
        backoff_ms: int = 200,
    ) -> RemotePinResult:
        ...


def _sleep_backoff(backoff_ms: int, attempt: int) -> None:
    if backoff_ms <= 0:
        return
    time.sleep((backoff_ms * (2 ** (attempt - 1))) / 1000.0)


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read()
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace").strip()


def _is_timeout_reason(reason: object) -> bool:
    if isinstance(reason, TimeoutError | socket.timeout):
        return True
    return "timed out" in str(reason).lower()


class PinningServiceAPIProvider:
    """Pinning Services API adapter.

    See https://ipfs.github.io/pinning-services-api-spec
    """

    provider_name = "psa"

    def __init__(self, *, endpoint: str, token: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._token = token

    def remote_add(
        self,
        cid: str,
        *,
        name: str | None = None,
        timeout_ms: int = 10_000,
        retries: int = 3,
        backoff_ms: int = 200,
    ) -> RemotePinResult:
        if retries < 1:
            raise ExternalToolError(
                "Remote pin retries must be >= 1.",
                code="HELIX_E_INVALID_OPTION",
                next_action="Use --retries with value >= 1.",
            )
        if timeout_ms < 1:
            raise ExternalToolError(
                "Remote pin timeout must be >= 1ms.",
                code="HELIX_E_INVALID_OPTION",
                next_action="Use --timeout-ms with value >= 1.",
            )
        if backoff_ms < 0:
            raise ExternalToolError(
                "Remote pin backoff must be >= 0ms.",
                code="HELIX_E_INVALID_OPTION",
                next_action="Use --backoff-ms with value >= 0.",
            )

        url = f"{self._endpoint}/pins"
        body = {"cid": cid}
        if name:
            body["name"] = name
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")

        request = urllib.request.Request(url=url, data=data, method="POST")
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")

        for attempt in range(1, retries + 1):
            try:
                timeout_s = timeout_ms / 1000.0
                with urllib.request.urlopen(
                    request, timeout=timeout_s,
                ) as response:
                    raw = response.read()
                return self._parse_success(raw, requested_cid=cid)
            except urllib.error.HTTPError as exc:
                payload = _read_http_error_body(exc)
                detail = payload or exc.reason

                if exc.code in {401, 403}:
                    msg = (
                        "Remote pin authorization "
                        f"failed (HTTP {exc.code}): "
                        f"{detail}"
                    )
                    raise ExternalToolError(
                        msg,
                        code="HELIX_E_REMOTE_PIN_AUTH",
                        next_action=(
                            "Verify remote pin API "
                            "token/permissions and retry."
                        ),
                    ) from exc

                retryable = exc.code >= 500 or exc.code == 429
                retryable = (
                    exc.code >= 500 or exc.code == 429
                )
                if retryable and attempt < retries:
                    _sleep_backoff(backoff_ms, attempt)
                    continue

                if 400 <= exc.code < 500:
                    msg = (
                        "Remote pin request rejected"
                        f" (HTTP {exc.code}): "
                        f"{detail}"
                    )
                    raise ExternalToolError(
                        msg,
                        code="HELIX_E_REMOTE_PIN_REQUEST",
                        next_action=(
                            "Check CID/provider options"
                            " and retry."
                        ),
                    ) from exc

                msg = (
                    "Remote pin request failed"
                    f" (HTTP {exc.code}): {detail}"
                )
                raise ExternalToolError(
                    msg,
                    code="HELIX_E_REMOTE_PIN",
                    next_action=(
                        "Retry remote pin or verify"
                        " provider availability."
                    ),
                ) from exc
            except urllib.error.URLError as exc:
                timeout_like = _is_timeout_reason(
                    exc.reason,
                )
                if attempt < retries:
                    _sleep_backoff(backoff_ms, attempt)
                    continue

                if timeout_like:
                    msg = (
                        "Remote pin timed out after"
                        f" {retries} attempt(s):"
                        f" {exc.reason}"
                    )
                    raise ExternalToolError(
                        msg,
                        code="HELIX_E_REMOTE_PIN_TIMEOUT",
                        next_action=(
                            "Increase timeout/retries"
                            " or verify provider"
                            " latency."
                        ),
                    ) from exc

                msg = (
                    "Remote pin request failed"
                    f" after {retries}"
                    f" attempt(s): {exc.reason}"
                )
                raise ExternalToolError(
                    msg,
                    code="HELIX_E_REMOTE_PIN",
                    next_action=(
                        "Verify provider endpoint/"
                        "network connectivity"
                        " and retry."
                    ),
                ) from exc
            except OSError as exc:
                if attempt < retries:
                    _sleep_backoff(backoff_ms, attempt)
                    continue
                msg = (
                    "Remote pin request failed"
                    f" after {retries}"
                    f" attempt(s): {exc}"
                )
                raise ExternalToolError(
                    msg,
                    code="HELIX_E_REMOTE_PIN",
                    next_action=(
                        "Verify local network path"
                        " to provider and retry."
                    ),
                ) from exc

        raise ExternalToolError(
            "Remote pin request failed unexpectedly"
            " without explicit error context.",
            code="HELIX_E_REMOTE_PIN",
            next_action=(
                "Retry remote pin and inspect"
                " provider/API logs."
            ),
        )

    def _parse_success(
        self, raw: bytes, *, requested_cid: str,
    ) -> RemotePinResult:
        if not raw:
            return RemotePinResult(
                provider=self.provider_name,
                cid=requested_cid,
                status="queued",
                request_id=None,
            )

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ExternalToolError(
                "Remote pin response is not"
                f" valid JSON: {exc}",
                code="HELIX_E_REMOTE_PIN",
                next_action=(
                    "Retry request or verify"
                    " provider API compatibility."
                ),
            ) from exc

        if not isinstance(payload, dict):
            raise ExternalToolError(
                "Remote pin response JSON"
                " must be an object.",
                code="HELIX_E_REMOTE_PIN",
                next_action=(
                    "Verify provider API"
                    " compatibility with"
                    " Pinning Services API."
                ),
            )

        status = payload.get("status")
        status_text = (
            status if isinstance(status, str) and status
            else "queued"
        )
        request_id = payload.get("requestid")
        req_is_str = isinstance(request_id, str)
        request_id_text = (
            request_id if req_is_str and request_id
            else None
        )

        cid = requested_cid
        pin_obj = payload.get("pin")
        if isinstance(pin_obj, dict):
            candidate = pin_obj.get("cid")
            if isinstance(candidate, str) and candidate:
                cid = candidate

        return RemotePinResult(
            provider=self.provider_name,
            cid=cid,
            status=status_text,
            request_id=request_id_text,
        )


def build_remote_pin_provider(
    provider: str,
    *,
    endpoint: str,
    token: str,
) -> RemotePinProvider:
    provider_key = provider.strip().lower()
    valid = {
        "psa", "pinning-service-api",
        "pinning_service_api",
    }
    if provider_key in valid:
        return PinningServiceAPIProvider(
            endpoint=endpoint, token=token,
        )

    raise ExternalToolError(
        f"Unsupported remote pin provider: {provider}",
        code="HELIX_E_INVALID_OPTION",
        next_action=(
            "Use --provider psa for Pinning"
            " Services API-compatible providers."
        ),
    )
