from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest
from typer.testing import CliRunner

from helix.cli import app
from helix.errors import ExternalToolError
from helix.ipfs import remote_pin_cid
from helix.pinning import PinningServiceAPIProvider, RemotePinResult


class _Resp:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN201
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_psa_provider_retries_then_succeeds(monkeypatch) -> None:
    calls = 0
    sleeps: list[float] = []

    def _fake_urlopen(req, timeout=0):  # noqa: ANN001, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                url=req.full_url,
                code=500,
                msg="server error",
                hdrs=None,
                fp=io.BytesIO(b"temporary outage"),
            )
        assert timeout == 10.0
        assert req.get_method() == "POST"
        assert json.loads(req.data.decode("utf-8")) == {"cid": "bafy-test", "name": "seed.hlx"}
        return _Resp(
            {
                "requestid": "req-1",
                "status": "queued",
                "pin": {"cid": "bafy-test"},
            }
        )

    monkeypatch.setattr("helix.pinning.urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setattr("helix.pinning.time.sleep", lambda s: sleeps.append(s))

    provider = PinningServiceAPIProvider(endpoint="https://pin.example/api/v1", token="token")
    report = provider.remote_add(
        "bafy-test",
        name="seed.hlx",
        timeout_ms=10_000,
        retries=2,
        backoff_ms=25,
    )

    assert report == RemotePinResult(
        provider="psa",
        cid="bafy-test",
        status="queued",
        request_id="req-1",
    )
    assert calls == 2
    assert sleeps == [0.025]


def test_psa_provider_maps_auth_failures(monkeypatch) -> None:
    def _fake_urlopen(req, timeout=0):  # noqa: ANN001, ANN202
        _ = timeout
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=401,
            msg="unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"unauthorized"),
        )

    monkeypatch.setattr("helix.pinning.urllib.request.urlopen", _fake_urlopen)

    provider = PinningServiceAPIProvider(endpoint="https://pin.example/api/v1", token="bad-token")
    with pytest.raises(ExternalToolError) as exc_info:
        provider.remote_add("bafy-test", retries=1, backoff_ms=0)
    assert exc_info.value.code == "HELIX_E_REMOTE_PIN_AUTH"


def test_remote_pin_cid_requires_endpoint_and_token(monkeypatch) -> None:
    monkeypatch.delenv("HELIX_PINNING_ENDPOINT", raising=False)
    monkeypatch.delenv("HELIX_PINNING_TOKEN", raising=False)

    with pytest.raises(ExternalToolError) as exc_info:
        remote_pin_cid("bafy-test")
    assert exc_info.value.code == "HELIX_E_REMOTE_PIN_CONFIG"


def test_publish_can_trigger_remote_pin(tmp_path: Path, monkeypatch) -> None:
    seed = tmp_path / "seed.hlx"
    seed.write_bytes(b"HLE1" + b"x" * 32)

    def _fake_publish(_seed: Path, pin: bool = False) -> str:
        assert pin is False
        return "bafy-cid"

    def _fake_remote_pin(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        return RemotePinResult(
            provider="psa",
            cid="bafy-cid",
            status="queued",
            request_id="req-42",
        )

    monkeypatch.setattr("helix.cli.publish_seed", _fake_publish)
    monkeypatch.setattr("helix.cli.remote_pin_cid", _fake_remote_pin)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "publish",
            str(seed),
            "--remote-pin",
            "--remote-endpoint",
            "https://pin.example/api/v1",
            "--remote-token",
            "token",
        ],
    )

    assert result.exit_code == 0
    assert "remote_pin provider=psa cid=bafy-cid status=queued request_id=req-42" in result.output
    assert result.output.strip().endswith("bafy-cid")


def test_pin_remote_add_cli_reports_error_code(monkeypatch) -> None:
    def _fail_remote_pin(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise ExternalToolError(
            "bad token",
            code="HELIX_E_REMOTE_PIN_AUTH",
            next_action="rotate token",
        )

    monkeypatch.setattr("helix.cli.remote_pin_cid", _fail_remote_pin)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "pin",
            "remote-add",
            "bafy-cid",
            "--endpoint",
            "https://pin.example/api/v1",
            "--token",
            "bad",
        ],
    )

    assert result.exit_code == 1
    assert "error[HELIX_E_REMOTE_PIN_AUTH]" in result.output
    assert "next_action: rotate token" in result.output
