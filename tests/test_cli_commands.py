from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from seedbraid import __version__
from seedbraid.cli import app
from seedbraid.codec import EncodeStats, VerifyReport
from seedbraid.errors import ExternalToolError, SeedbraidError

runner = CliRunner()


# ---------------------------------------------------------------------------
# _cfg validation
# ---------------------------------------------------------------------------


def test_cfg_rejects_negative_sizes(tmp_path: Path) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x")
    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "s.sbd"),
            "--avg",
            "-1",
        ],
    )
    assert result.exit_code != 0


def test_cfg_rejects_invalid_ordering(tmp_path: Path) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x")
    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "s.sbd"),
            "--min",
            "1000",
            "--avg",
            "500",
            "--max",
            "2000",
        ],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# encode
# ---------------------------------------------------------------------------


def test_encode_success_output(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x" * 100)

    monkeypatch.setattr(
        "seedbraid.cli.encode_file",
        lambda **kw: EncodeStats(
            total_chunks=10,
            reused_chunks=5,
            new_chunks=3,
            raw_chunks=2,
            unique_hashes=8,
        ),
    )

    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "s.sbd"),
        ],
    )
    assert result.exit_code == 0
    assert "encoded" in result.output
    assert "chunks=10" in result.output
    assert "reused=5" in result.output


def test_encode_error_handling(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x")

    def _fail(**kw):
        raise SeedbraidError("encode boom", code="SB_E_TEST")

    monkeypatch.setattr("seedbraid.cli.encode_file", _fail)

    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "s.sbd"),
        ],
    )
    assert result.exit_code == 1
    assert "error[SB_E_TEST]" in result.output


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------


def test_decode_success_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.decode_file",
        lambda *a, **kw: "abcd1234",
    )

    result = runner.invoke(
        app,
        [
            "decode",
            str(tmp_path / "s.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "out.bin"),
        ],
    )
    assert result.exit_code == 0
    assert "decoded sha256=abcd1234" in result.output


def test_decode_error_handling(tmp_path: Path, monkeypatch) -> None:
    def _fail(*a, **kw):
        raise SeedbraidError("decode boom", code="SB_E_TEST")

    monkeypatch.setattr("seedbraid.cli.decode_file", _fail)

    result = runner.invoke(
        app,
        [
            "decode",
            str(tmp_path / "s.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "out.bin"),
        ],
    )
    assert result.exit_code == 1
    assert "error[SB_E_TEST]" in result.output


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def test_verify_ok_quick_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.verify_seed",
        lambda *a, **kw: VerifyReport(
            ok=True,
            missing_hashes=[],
            missing_count=0,
            expected_sha256="aaa",
            actual_sha256="aaa",
            reason=None,
        ),
    )

    result = runner.invoke(
        app,
        ["verify", str(tmp_path / "s.sbd"), "--genome", str(tmp_path / "g")],
    )
    assert result.exit_code == 0
    assert "verify ok mode=quick" in result.output
    assert "expected_sha256=aaa" in result.output


def test_verify_ok_strict_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.verify_seed",
        lambda *a, **kw: VerifyReport(
            ok=True,
            missing_hashes=[],
            missing_count=0,
            expected_sha256="bbb",
            actual_sha256="bbb",
            reason=None,
        ),
    )

    result = runner.invoke(
        app,
        [
            "verify",
            str(tmp_path / "s.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--strict",
        ],
    )
    assert result.exit_code == 0
    assert "verify ok mode=strict" in result.output


def test_verify_failed_with_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.verify_seed",
        lambda *a, **kw: VerifyReport(
            ok=False,
            missing_hashes=["h1", "h2"],
            missing_count=2,
            expected_sha256=None,
            actual_sha256=None,
            reason="chunks missing",
        ),
    )

    result = runner.invoke(
        app,
        ["verify", str(tmp_path / "s.sbd"), "--genome", str(tmp_path / "g")],
    )
    assert result.exit_code == 1
    assert "verify failed" in result.output
    assert "missing_count=2" in result.output
    assert "missing_chunk=h1" in result.output


def test_verify_failed_with_sha256_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.verify_seed",
        lambda *a, **kw: VerifyReport(
            ok=False,
            missing_hashes=[],
            missing_count=0,
            expected_sha256="aaa",
            actual_sha256="bbb",
            reason="sha256 mismatch",
        ),
    )

    result = runner.invoke(
        app,
        ["verify", str(tmp_path / "s.sbd"), "--genome", str(tmp_path / "g")],
    )
    assert result.exit_code == 1
    assert "expected_sha256=aaa" in result.output
    assert "actual_sha256=bbb" in result.output


# ---------------------------------------------------------------------------
# prime
# ---------------------------------------------------------------------------


def test_prime_success_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.prime_genome",
        lambda **kw: {
            "files": 3,
            "total_chunks": 20,
            "new_chunks": 15,
            "reused_chunks": 5,
            "dedup_ratio_bps": 2500,
        },
    )

    result = runner.invoke(
        app,
        ["prime", str(tmp_path), "--genome", str(tmp_path / "g")],
    )
    assert result.exit_code == 0
    assert "prime" in result.output
    assert "files=3" in result.output
    assert "25.00%" in result.output


def test_prime_error_handling(tmp_path: Path, monkeypatch) -> None:
    def _fail(**kw):
        raise SeedbraidError("prime boom", code="SB_E_TEST")

    monkeypatch.setattr("seedbraid.cli.prime_genome", _fail)

    result = runner.invoke(
        app,
        ["prime", str(tmp_path), "--genome", str(tmp_path / "g")],
    )
    assert result.exit_code == 1
    assert "error[SB_E_TEST]" in result.output


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


def test_fetch_success_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("seedbraid.cli.fetch_seed", lambda *a, **kw: None)

    result = runner.invoke(
        app,
        ["fetch", "QmTest123", "--out", str(tmp_path / "seed.sbd")],
    )
    assert result.exit_code == 0
    assert "fetched QmTest123" in result.output


def test_fetch_error_handling(tmp_path: Path, monkeypatch) -> None:
    def _fail(*a, **kw):
        raise ExternalToolError("ipfs down", code="SB_E_IPFS")

    monkeypatch.setattr("seedbraid.cli.fetch_seed", _fail)

    result = runner.invoke(
        app,
        ["fetch", "QmTest123", "--out", str(tmp_path / "seed.sbd")],
    )
    assert result.exit_code == 1
    assert "error[SB_E_IPFS]" in result.output


# ---------------------------------------------------------------------------
# sign
# ---------------------------------------------------------------------------


def test_sign_missing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SB_SIGNING_KEY", raising=False)

    result = runner.invoke(
        app,
        [
            "sign",
            str(tmp_path / "s.sbd"),
            "--out",
            str(tmp_path / "signed.sbd"),
        ],
    )
    assert result.exit_code == 1
    assert "error[SB_E_SIGNING_KEY_MISSING]" in result.output


def test_sign_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SB_SIGNING_KEY", "test-key-123")
    monkeypatch.setattr("seedbraid.cli.sign_seed_file", lambda *a, **kw: None)

    result = runner.invoke(
        app,
        [
            "sign",
            str(tmp_path / "s.sbd"),
            "--out",
            str(tmp_path / "signed.sbd"),
        ],
    )
    assert result.exit_code == 0
    assert "signed" in result.output
    assert "key_id=default" in result.output


# ---------------------------------------------------------------------------
# export-genes / import-genes
# ---------------------------------------------------------------------------


def test_export_genes_cli_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.export_genes",
        lambda *a, **kw: {"total": 10, "exported": 8, "missing": 2},
    )

    result = runner.invoke(
        app,
        [
            "export-genes",
            str(tmp_path / "s.sbd"),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "genes.pak"),
        ],
    )
    assert result.exit_code == 0
    assert "exported total=10 exported=8 missing=2" in result.output


def test_import_genes_cli_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.import_genes",
        lambda *a, **kw: {"inserted": 7, "skipped": 3},
    )

    result = runner.invoke(
        app,
        [
            "import-genes",
            str(tmp_path / "genes.pak"),
            "--genome",
            str(tmp_path / "g"),
        ],
    )
    assert result.exit_code == 0
    assert "imported inserted=7 skipped=3" in result.output


# ---------------------------------------------------------------------------
# genome snapshot / restore
# ---------------------------------------------------------------------------


def test_genome_snapshot_cli_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.snapshot_genome",
        lambda *a, **kw: {"chunks": 50, "bytes": 102400},
    )

    result = runner.invoke(
        app,
        [
            "genome",
            "snapshot",
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "snap.bin"),
        ],
    )
    assert result.exit_code == 0
    assert "snapshot chunks=50 bytes=102400" in result.output


def test_genome_restore_cli_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seedbraid.cli.restore_genome",
        lambda *a, **kw: {"entries": 50, "inserted": 45, "skipped": 5},
    )

    result = runner.invoke(
        app,
        [
            "genome",
            "restore",
            str(tmp_path / "snap.bin"),
            "--genome",
            str(tmp_path / "g"),
        ],
    )
    assert result.exit_code == 0
    assert "restored entries=50 inserted=45 skipped=5" in result.output


# ---------------------------------------------------------------------------
# _print_error non-SeedbraidError fallback
# ---------------------------------------------------------------------------


def test_print_error_unknown_exception(tmp_path: Path, monkeypatch) -> None:
    def _fail(**kw):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("seedbraid.cli.encode_file", _fail)

    src = tmp_path / "f.bin"
    src.write_bytes(b"x")
    result = runner.invoke(
        app,
        [
            "encode",
            str(src),
            "--genome",
            str(tmp_path / "g"),
            "--out",
            str(tmp_path / "s.sbd"),
        ],
    )
    # RuntimeError is not caught by the except SeedbraidError
    # clause, so it propagates. The CLI runner captures
    # the traceback.
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# --version flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_flag_shows_version(flag: str) -> None:
    result = runner.invoke(app, [flag])
    assert result.exit_code == 0
    assert __version__ in result.output
