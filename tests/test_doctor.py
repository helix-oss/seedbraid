from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from helix.cli import app
from helix.diagnostics import (
    DoctorCheck,
    DoctorReport,
    _check_compression,
    _check_ipfs_cli,
    _check_ipfs_path,
    run_doctor,
)
from helix.errors import ExternalToolError, HelixError


def test_doctor_cli_exit_zero_with_only_warn(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.cli.run_doctor",
        lambda _genome: DoctorReport(
            checks=[
                DoctorCheck(check="python", status="ok", detail="python=3.12"),
                DoctorCheck(
                    check="compression_zstd",
                    status="warn",
                    detail="zstandard missing",
                    next_action="install zstandard",
                ),
            ]
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "[ok] python: python=3.12" in result.output
    assert "[warn] compression_zstd: zstandard missing" in result.output
    assert "doctor summary ok=1 warn=1 fail=0" in result.output


def test_doctor_cli_exit_one_on_fail(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.cli.run_doctor",
        lambda _genome: DoctorReport(
            checks=[
                DoctorCheck(
                    check="ipfs_cli",
                    status="fail",
                    detail="ipfs missing",
                    next_action="install kubo",
                )
            ]
        ),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "[fail] ipfs_cli: ipfs missing" in result.output
    assert "next_action: install kubo" in result.output


def test_run_doctor_flags_missing_ipfs(tmp_path: Path, monkeypatch) -> None:
    genome = tmp_path / "genome"
    monkeypatch.setattr("helix.diagnostics.shutil.which", lambda _name: None)
    monkeypatch.delenv("IPFS_PATH", raising=False)

    report = run_doctor(genome)
    ipfs = next(c for c in report.checks if c.check == "ipfs_cli")

    assert ipfs.status == "fail"
    assert report.fail_count >= 1


def test_error_output_includes_code_and_next_action(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "input.bin"
    src.write_bytes(b"x")
    monkeypatch.delenv("HELIX_ENCRYPTION_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "genome"),
            "--out",
            str(tmp_path / "seed.hlx"),
            "--encrypt",
        ],
    )

    assert result.exit_code == 1
    assert "error[HELIX_E_ENCRYPTION_KEY_MISSING]" in result.output
    assert "next_action:" in result.output


# ---------------------------------------------------------------------------
# _check_ipfs_cli: success path
# ---------------------------------------------------------------------------


def test_check_ipfs_cli_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.diagnostics.shutil.which", lambda _: "/usr/bin/ipfs"
    )
    monkeypatch.setattr(
        "helix.diagnostics.subprocess.run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd,
            returncode=0,
            stdout="ipfs version 0.20.0\n",
            stderr="",
        ),
    )
    check = _check_ipfs_cli()
    assert check.status == "ok"
    assert "0.20.0" in check.detail


def test_check_ipfs_cli_fails_on_returncode(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.diagnostics.shutil.which", lambda _: "/usr/bin/ipfs"
    )
    monkeypatch.setattr(
        "helix.diagnostics.subprocess.run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd,
            returncode=1,
            stdout="",
            stderr="permission denied",
        ),
    )
    check = _check_ipfs_cli()
    assert check.status == "fail"
    assert "permission denied" in check.detail


# ---------------------------------------------------------------------------
# _check_ipfs_path: various scenarios
# ---------------------------------------------------------------------------


def test_check_ipfs_path_nonexistent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IPFS_PATH", str(tmp_path / "nonexistent"))
    check = _check_ipfs_path()
    assert check.status == "warn"
    assert "does not exist" in check.detail


def test_check_ipfs_path_is_file(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "ipfs_file"
    f.write_text("not a dir")
    monkeypatch.setenv("IPFS_PATH", str(f))
    check = _check_ipfs_path()
    assert check.status == "fail"
    assert "not a directory" in check.detail


def test_check_ipfs_path_valid_dir(tmp_path: Path, monkeypatch) -> None:
    d = tmp_path / "ipfs_repo"
    d.mkdir()
    monkeypatch.setenv("IPFS_PATH", str(d))
    check = _check_ipfs_path()
    assert check.status == "ok"
    assert str(d) in check.detail


# ---------------------------------------------------------------------------
# _check_compression: zstandard available
# ---------------------------------------------------------------------------


def test_check_compression_zstandard_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.diagnostics.importlib.util.find_spec",
        lambda name: object(),  # non-None → available
    )
    checks = _check_compression()
    zstd = next(c for c in checks if c.check == "compression_zstd")
    assert zstd.status == "ok"
    assert "available" in zstd.detail


# ---------------------------------------------------------------------------
# run_doctor: exception handling
# ---------------------------------------------------------------------------


def test_run_doctor_reraises_helix_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.diagnostics._check_python_version",
        lambda: (_ for _ in ()).throw(HelixError("test", code="TEST")),
    )
    with pytest.raises(HelixError, match="test"):
        run_doctor(tmp_path)


def test_run_doctor_wraps_unexpected_exception(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "helix.diagnostics._check_ipfs_cli",
        lambda: (_ for _ in ()).throw(ValueError("unexpected")),
    )
    with pytest.raises(ExternalToolError, match="doctor failed unexpectedly"):
        run_doctor(tmp_path)
