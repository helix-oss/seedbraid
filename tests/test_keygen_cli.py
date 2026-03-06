from __future__ import annotations

from typer.testing import CliRunner

from helix.cli import app


def test_gen_encryption_key_prints_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.cli.secrets.token_urlsafe", lambda _n: "generated-token"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["gen-encryption-key"])

    assert result.exit_code == 0
    assert result.output.strip() == "generated-token"


def test_gen_encryption_key_shell_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.cli.secrets.token_urlsafe", lambda _n: "shell-token"
    )

    runner = CliRunner()
    result = runner.invoke(app, ["gen-encryption-key", "--shell"])

    assert result.exit_code == 0
    assert result.output.strip() == "export HELIX_ENCRYPTION_KEY='shell-token'"


def test_gen_encryption_key_rejects_invalid_env_var(monkeypatch) -> None:
    monkeypatch.setattr(
        "helix.cli.secrets.token_urlsafe", lambda _n: "ignored-token"
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["gen-encryption-key", "--shell", "--env-var", "BAD-NAME"],
    )

    assert result.exit_code == 1
    assert "error[HELIX_E_INVALID_OPTION]" in result.output
    assert "next_action:" in result.output


def test_gen_encryption_key_forwards_bytes_value(monkeypatch) -> None:
    captured: dict[str, int] = {}

    def _fake_token_urlsafe(n: int) -> str:
        captured["bytes"] = n
        return "bytes-token"

    monkeypatch.setattr("helix.cli.secrets.token_urlsafe", _fake_token_urlsafe)

    runner = CliRunner()
    result = runner.invoke(app, ["gen-encryption-key", "--bytes", "48"])

    assert result.exit_code == 0
    assert captured["bytes"] == 48
    assert result.output.strip() == "bytes-token"
