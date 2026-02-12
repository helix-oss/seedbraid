from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typer.testing import CliRunner

from helix.cli import app
from helix.container import OP_RAW, Recipe, RecipeOp, serialize_seed
from helix.ipfs import fetch_seed, pin_health_status


@dataclass
class _Proc:
    returncode: int
    stdout: bytes | str
    stderr: bytes | str


def _minimal_seed_bytes() -> bytes:
    manifest = {
        "format": "HLX1",
        "version": 1,
        "manifest_private": True,
        "source_size": None,
        "source_sha256": None,
        "chunker": {"name": "fixed"},
        "portable": True,
        "learn": True,
    }
    recipe = Recipe(hash_table=[b"\x00" * 32], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)])
    return serialize_seed(manifest, recipe, {0: b"abc"}, manifest_compression="zlib")


def test_fetch_retries_and_succeeds_on_second_attempt(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "fetched.hlx"
    seed_blob = _minimal_seed_bytes()
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def _fake_run(cmd, check=False, capture_output=False, text=False):  # noqa: ANN001, ANN202
        calls.append(cmd)
        if len(calls) == 1:
            return _Proc(returncode=1, stdout=b"", stderr=b"temporary ipfs failure")
        return _Proc(returncode=0, stdout=seed_blob, stderr=b"")

    monkeypatch.setattr("helix.ipfs.shutil.which", lambda _name: "/usr/bin/ipfs")
    monkeypatch.setattr("helix.ipfs.subprocess.run", _fake_run)
    monkeypatch.setattr("helix.ipfs.time.sleep", lambda s: sleeps.append(s))

    fetch_seed("bafy-retry", out, retries=2, backoff_ms=10)

    assert out.read_bytes() == seed_blob
    assert sleeps == [0.01]


def test_fetch_uses_gateway_fallback_after_retry_exhaustion(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "fetched.hlx"
    seed_blob = _minimal_seed_bytes()
    requested_urls: list[str] = []

    def _fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        return _Proc(returncode=1, stdout=b"", stderr=b"offline")

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

    monkeypatch.setattr("helix.ipfs.shutil.which", lambda _name: "/usr/bin/ipfs")
    monkeypatch.setattr("helix.ipfs.subprocess.run", _fake_run)
    monkeypatch.setattr("helix.ipfs.urllib.request.urlopen", _fake_urlopen)

    fetch_seed("bafy-gw", out, retries=2, backoff_ms=0, gateway="https://gw.example/ipfs")
    assert out.read_bytes() == seed_blob
    assert requested_urls == ["https://gw.example/ipfs/bafy-gw"]


def test_pin_health_status_reports_ok_and_not_ok(monkeypatch) -> None:
    queued = [
        _Proc(returncode=0, stdout="bafy-ok recursive\n", stderr=""),
        _Proc(returncode=0, stdout="Key: bafy-ok\nSize: 1024\n", stderr=""),
        _Proc(returncode=1, stdout="", stderr="bafy-miss is not pinned"),
        _Proc(returncode=1, stdout="", stderr="block not found"),
    ]

    def _fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        return queued.pop(0)

    monkeypatch.setattr("helix.ipfs.shutil.which", lambda _name: "/usr/bin/ipfs")
    monkeypatch.setattr("helix.ipfs.subprocess.run", _fake_run)

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
        "helix.cli.pin_health_status",
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
        "helix.cli.pin_health_status",
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
