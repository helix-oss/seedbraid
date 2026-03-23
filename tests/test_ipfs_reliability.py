from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from seedbraid.cli import app
from seedbraid.container import OP_RAW, Recipe, RecipeOp, serialize_seed
from seedbraid.errors import ExternalToolError
from seedbraid.ipfs import fetch_seed, pin_health_status


def _minimal_seed_bytes() -> bytes:
    manifest = {
        "format": "SBD1",
        "version": 1,
        "manifest_private": True,
        "source_size": None,
        "source_sha256": None,
        "chunker": {"name": "fixed"},
        "portable": True,
        "learn": True,
    }
    recipe = Recipe(
        hash_table=[b"\x00" * 32], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)]
    )
    return serialize_seed(
        manifest, recipe, {0: b"abc"}, manifest_compression="zlib"
    )


def test_fetch_retries_and_succeeds_on_second_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "fetched.sbd"
    seed_blob = _minimal_seed_bytes()
    call_count = [0]
    sleeps: list[float] = []

    def _fake_post_raw(path, **params):  # noqa: ANN001, ANN003, ANN202
        call_count[0] += 1
        if call_count[0] == 1:
            raise ExternalToolError(
                "temporary ipfs failure",
                code="SB_E_KUBO_API_ERROR",
                next_action="retry",
            )
        return seed_blob

    monkeypatch.setattr("seedbraid.ipfs_http.post_raw", _fake_post_raw)
    monkeypatch.setattr(
        "seedbraid.ipfs.time.sleep",
        lambda s: sleeps.append(s),
    )

    fetch_seed("bafy-retry", out, retries=2, backoff_ms=10)

    assert out.read_bytes() == seed_blob
    assert sleeps == [0.01]


def test_fetch_uses_gateway_fallback_after_retry_exhaustion(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "fetched.sbd"
    seed_blob = _minimal_seed_bytes()
    requested_urls: list[str] = []

    def _always_fail(path, **params):  # noqa: ANN001, ANN003, ANN202
        raise ExternalToolError(
            "offline",
            code="SB_E_KUBO_API_ERROR",
        )

    class _Resp:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN201
            return False

        def read(self) -> bytes:
            return self._data

    def _fake_urlopen(url, timeout=30):  # noqa: ANN001, ANN202
        requested_urls.append(url)
        assert timeout == 30
        return _Resp(seed_blob)

    monkeypatch.setattr("seedbraid.ipfs_http.post_raw", _always_fail)
    monkeypatch.setattr("seedbraid.ipfs.urllib.request.urlopen", _fake_urlopen)

    fetch_seed(
        "bafy-gw",
        out,
        retries=2,
        backoff_ms=0,
        gateway="https://gw.example/ipfs",
    )
    assert out.read_bytes() == seed_blob
    assert requested_urls == ["https://gw.example/ipfs/bafy-gw"]


def test_pin_health_status_reports_ok_and_not_ok(monkeypatch) -> None:
    def _fake_post_json(path, **params):  # noqa: ANN001, ANN003, ANN202
        cid = params.get("arg", "")
        if path == "/pin/ls":
            if cid == "bafy-ok":
                return {
                    "Keys": {
                        "bafy-ok": {"Type": "recursive"},
                    }
                }
            raise ExternalToolError(
                "bafy-miss is not pinned",
                code="SB_E_KUBO_API_ERROR",
            )
        if path == "/block/stat":
            if cid == "bafy-ok":
                return {"Key": cid, "Size": 1024}
            raise ExternalToolError(
                "block not found",
                code="SB_E_KUBO_API_ERROR",
            )
        return {}

    monkeypatch.setattr("seedbraid.ipfs_http.post_json", _fake_post_json)

    ok_report = pin_health_status("bafy-ok")
    miss_report = pin_health_status("bafy-miss")

    assert ok_report["ok"] is True
    assert ok_report["pinned"] is True
    assert ok_report["pin_type"] == "recursive"
    assert ok_report["block_available"] is True

    assert miss_report["ok"] is False
    assert miss_report["pinned"] is False
    assert miss_report["block_available"] is False
    assert "not pinned" in str(miss_report["reason"])
    assert "block not found" in str(miss_report["reason"])


def test_pin_health_cli_exit_codes(monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.pin_health_status",
        lambda cid: {
            "cid": cid,
            "pinned": True,
            "pin_type": "recursive",
            "block_available": True,
            "ok": True,
            "reason": None,
        },
    )
    runner = CliRunner()
    ok = runner.invoke(app, ["pin-health", "bafy-ok"])
    assert ok.exit_code == 0
    assert "pinned=True" in ok.output

    monkeypatch.setattr(
        "seedbraid.cli.pin_health_status",
        lambda cid: {
            "cid": cid,
            "pinned": False,
            "pin_type": None,
            "block_available": False,
            "ok": False,
            "reason": "not pinned",
        },
    )
    miss = runner.invoke(app, ["pin-health", "bafy-miss"])
    assert miss.exit_code == 1
    assert "reason=not pinned" in miss.output
