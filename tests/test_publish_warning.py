from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from helix.cli import app


def test_publish_warns_for_unencrypted_seed(
    tmp_path: Path, monkeypatch
) -> None:
    seed = tmp_path / "plain.hlx"
    seed.write_bytes(b"HLX1" + b"x" * 64)
    monkeypatch.setattr(
        "helix.cli.publish_seed", lambda _seed, pin=False: "bafyplain"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["publish", str(seed), "--no-pin"])

    assert result.exit_code == 0
    assert "bafyplain" in result.output
    assert "warning: publishing unencrypted seed" in result.output


def test_publish_skips_warning_for_encrypted_seed(
    tmp_path: Path, monkeypatch
) -> None:
    seed = tmp_path / "encrypted.hlx"
    seed.write_bytes(b"HLE1" + b"x" * 64)
    monkeypatch.setattr(
        "helix.cli.publish_seed", lambda _seed, pin=False: "bafyencrypted"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["publish", str(seed), "--no-pin"])

    assert result.exit_code == 0
    assert "bafyencrypted" in result.output
    assert "warning: publishing unencrypted seed" not in result.output
