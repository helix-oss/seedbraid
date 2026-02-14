from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from helix.container import OP_RAW, Recipe, RecipeOp, serialize_seed
from helix.errors import ExternalToolError
from helix.mlhooks import (
    build_seed_metadata,
    log_seed_metadata_to_mlflow,
    upload_seed_and_metadata_to_hf,
    write_seed_metadata,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ML_EXAMPLE_DIR = REPO_ROOT / "examples" / "ml"


@dataclass
class _Proc:
    returncode: int
    stdout: str
    stderr: str


def _write_seed(tmp_path: Path, *, manifest_private: bool) -> Path:
    manifest = {
        "format": "HLX1",
        "version": 1,
        "source_size": None if manifest_private else 5,
        "source_sha256": None if manifest_private else "deadbeef",
        "chunker": {"name": "cdc_buzhash"},
        "portable": True,
        "learn": True,
        "manifest_private": manifest_private,
    }
    recipe = Recipe(hash_table=[b"\x00" * 32], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)])
    seed_bytes = serialize_seed(manifest, recipe, {0: b"chunk"}, manifest_compression="zlib")
    seed_path = tmp_path / "seed.hlx"
    seed_path.write_bytes(seed_bytes)
    return seed_path


def test_build_seed_metadata_includes_restore_fields(tmp_path: Path) -> None:
    seed_path = _write_seed(tmp_path, manifest_private=False)

    metadata = build_seed_metadata(
        seed_path,
        cid="bafyseed",
        oci_reference="ghcr.io/acme/helix-seed:v1",
    )

    assert metadata["seed_file"] == "seed.hlx"
    assert metadata["seed_sha256"]
    assert metadata["source_sha256"] == "deadbeef"
    assert metadata["chunker"] == "cdc_buzhash"
    assert metadata["manifest_private"] is False
    assert metadata["ipfs_cid"] == "bafyseed"
    assert metadata["oci_reference"] == "ghcr.io/acme/helix-seed:v1"


def test_log_seed_metadata_to_mlflow_creates_experiment_and_run(monkeypatch) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _fake_request(method, url, *, payload, token, timeout_s, not_found_ok=False):  # noqa: ANN001, ANN202
        calls.append((method, url, payload))
        assert token == "ml-token"
        assert timeout_s == 10.0

        if "experiments/get-by-name" in url:
            assert not_found_ok is True
            return None
        if url.endswith("/experiments/create"):
            return {"experiment_id": "42"}
        if url.endswith("/runs/create"):
            assert payload == {"experiment_id": "42", "run_name": "seed-run"}
            return {"run": {"info": {"run_id": "run-1"}}}
        if url.endswith("/runs/log-batch"):
            assert payload is not None
            assert payload["run_id"] == "run-1"
            params = {item["key"]: item["value"] for item in payload["params"]}
            assert params["manifest_private"] == "false"
            assert params["seed_sha256"] == "abc"
            return {}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("helix.mlhooks._request_json", _fake_request)

    result = log_seed_metadata_to_mlflow(
        {"seed_sha256": "abc", "manifest_private": False},
        tracking_uri="https://mlflow.example",
        experiment_name="helix-seeds",
        run_name="seed-run",
        token="ml-token",
        timeout_s=10.0,
    )

    assert result.experiment_id == "42"
    assert result.run_id == "run-1"
    assert len(calls) == 4


def test_upload_seed_and_metadata_to_hf_invokes_cli_twice(tmp_path: Path, monkeypatch) -> None:
    seed_path = _write_seed(tmp_path, manifest_private=True)
    metadata_path = write_seed_metadata({"seed_sha256": "abc"}, tmp_path / "seed.hlx.metadata.json")

    calls: list[tuple[list[str], str | None]] = []

    def _fake_run(cmd, check=False, text=True, capture_output=True, env=None):  # noqa: ANN001, ANN202
        calls.append((cmd, None if env is None else env.get("HF_TOKEN")))
        return _Proc(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("helix.mlhooks._resolve_hf_cli", lambda: ["huggingface-cli", "upload"])
    monkeypatch.setattr("helix.mlhooks.subprocess.run", _fake_run)

    result = upload_seed_and_metadata_to_hf(
        repo_id="acme/helix-seeds",
        seed_path=seed_path,
        metadata_path=metadata_path,
        repo_type="dataset",
        revision="main",
        remote_prefix="helix/seeds",
        token="hf-token",
    )

    assert result.seed_remote_path.endswith("seed.hlx")
    assert result.metadata_remote_path.endswith("seed.hlx.metadata.json")
    assert len(calls) == 2
    assert calls[0][1] == "hf-token"
    assert calls[1][1] == "hf-token"


def test_upload_seed_and_metadata_to_hf_requires_token(tmp_path: Path, monkeypatch) -> None:
    seed_path = _write_seed(tmp_path, manifest_private=True)
    metadata_path = write_seed_metadata({"seed_sha256": "abc"}, tmp_path / "seed.hlx.metadata.json")

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACEHUB_API_TOKEN", raising=False)

    with pytest.raises(ExternalToolError, match="token is required") as exc:
        upload_seed_and_metadata_to_hf(
            repo_id="acme/helix-seeds",
            seed_path=seed_path,
            metadata_path=metadata_path,
        )

    assert exc.value.code == "HELIX_E_HF_CONFIG"


def test_readme_links_ml_hooks_section() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    assert "## ML Tooling Hooks (HLX-ECO-005)" in readme
    assert "examples/ml/README.md" in readme


def test_ml_example_documents_restore_and_security() -> None:
    ml_readme = (ML_EXAMPLE_DIR / "README.md").read_text()
    assert "## Restore from Logged Metadata" in ml_readme
    assert "helix verify ./seed.hlx --genome ./genome --strict" in ml_readme
    assert "## Security Caveats" in ml_readme
    assert "manifest-private" in ml_readme
