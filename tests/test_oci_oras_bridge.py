from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from seedbraid.container import OP_RAW, Recipe, RecipeOp, serialize_seed
from seedbraid.errors import ExternalToolError
from seedbraid.oci import (
    ANNOTATION_CHUNKER,
    ANNOTATION_MANIFEST_PRIVATE,
    ANNOTATION_SOURCE_SHA256,
    ANNOTATION_TITLE,
    SB_OCI_SEED_MEDIA_TYPE,
    build_oras_annotations,
    pull_seed_oras,
    push_seed_oras,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OCI_EXAMPLE_DIR = REPO_ROOT / "examples" / "oci"


@dataclass
class _Proc:
    returncode: int
    stdout: str
    stderr: str


def _write_seed(tmp_path: Path, manifest: dict) -> Path:
    recipe = Recipe(
        hash_table=[b"\x00" * 32], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)]
    )
    seed_bytes = serialize_seed(
        manifest=manifest,
        recipe=recipe,
        raw_payloads={0: b"chunk"},
        manifest_compression="zlib",
    )
    seed_path = tmp_path / "seed.sbd"
    seed_path.write_bytes(seed_bytes)
    return seed_path


def test_build_oras_annotations_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "format": "SBD1",
        "version": 1,
        "source_size": 5,
        "source_sha256": "deadbeef",
        "chunker": {"name": "cdc_buzhash"},
        "portable": True,
        "learn": True,
        "manifest_private": False,
    }
    seed_path = _write_seed(tmp_path, manifest)

    annotations = build_oras_annotations(seed_path)

    assert annotations[ANNOTATION_SOURCE_SHA256] == "deadbeef"
    assert annotations[ANNOTATION_CHUNKER] == "cdc_buzhash"
    assert annotations[ANNOTATION_MANIFEST_PRIVATE] == "false"
    assert annotations[ANNOTATION_TITLE] == "seed.sbd"


def test_build_oras_annotations_handles_private_manifest(
    tmp_path: Path,
) -> None:
    manifest = {
        "format": "SBD1",
        "version": 1,
        "source_size": None,
        "source_sha256": None,
        "chunker": {"name": "fixed"},
        "portable": True,
        "learn": True,
        "manifest_private": True,
    }
    seed_path = _write_seed(tmp_path, manifest)

    annotations = build_oras_annotations(seed_path)

    assert annotations[ANNOTATION_SOURCE_SHA256] == "null"
    assert annotations[ANNOTATION_CHUNKER] == "fixed"
    assert annotations[ANNOTATION_MANIFEST_PRIVATE] == "true"


def test_push_seed_oras_builds_expected_command(
    tmp_path: Path, monkeypatch
) -> None:
    seed_path = tmp_path / "seed.sbd"
    seed_path.write_bytes(b"SBD1" + b"x" * 32)
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        "seedbraid.oci._require_oras_cli",
        lambda: "/usr/bin/oras",
    )
    monkeypatch.setattr(
        "seedbraid.oci.build_oras_annotations",
        lambda *_args, **_kwargs: {
            ANNOTATION_SOURCE_SHA256: "abc",
            ANNOTATION_CHUNKER: "cdc_buzhash",
            ANNOTATION_MANIFEST_PRIVATE: "false",
            ANNOTATION_TITLE: "seed.sbd",
        },
    )

    def _fake_run(cmd, check=False, text=True, capture_output=True, cwd=None):  # noqa: ANN001, ANN202
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return _Proc(returncode=0, stdout="pushed", stderr="")

    monkeypatch.setattr("seedbraid.oci.subprocess.run", _fake_run)

    annotations = push_seed_oras(
        seed_path, "ghcr.io/acme/seedbraid-seed:latest"
    )

    cmd = calls["cmd"]
    assert isinstance(cmd, list)
    assert f"seed.sbd:{SB_OCI_SEED_MEDIA_TYPE}" in cmd
    assert str(seed_path) not in " ".join(cmd)
    assert calls["cwd"] == seed_path.parent
    assert annotations[ANNOTATION_SOURCE_SHA256] == "abc"


def test_pull_seed_oras_restores_single_sbd_payload(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "seedbraid.oci._require_oras_cli",
        lambda: "/usr/bin/oras",
    )

    def _fake_run(cmd, check=False, text=True, capture_output=True):  # noqa: ANN001, ANN202
        out_index = cmd.index("-o") + 1
        pulled_dir = Path(cmd[out_index])
        pulled_file = pulled_dir / "restored.sbd"
        pulled_file.parent.mkdir(parents=True, exist_ok=True)
        pulled_file.write_bytes(b"SBD1pulled")
        return _Proc(returncode=0, stdout="pulled", stderr="")

    monkeypatch.setattr("seedbraid.oci.subprocess.run", _fake_run)

    out_path = tmp_path / "out" / "seed.sbd"
    pull_seed_oras("ghcr.io/acme/seedbraid-seed:latest", out_path)

    assert out_path.read_bytes() == b"SBD1pulled"


def test_pull_seed_oras_fails_when_multiple_sbd_payloads(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "seedbraid.oci._require_oras_cli",
        lambda: "/usr/bin/oras",
    )

    def _fake_run(cmd, check=False, text=True, capture_output=True):  # noqa: ANN001, ANN202
        out_index = cmd.index("-o") + 1
        pulled_dir = Path(cmd[out_index])
        (pulled_dir / "a.sbd").write_bytes(b"a")
        (pulled_dir / "b.sbd").write_bytes(b"b")
        return _Proc(returncode=0, stdout="pulled", stderr="")

    monkeypatch.setattr("seedbraid.oci.subprocess.run", _fake_run)

    with pytest.raises(
        ExternalToolError,
        match="exactly one `.sbd` payload",
    ):
        pull_seed_oras(
            "ghcr.io/acme/seedbraid-seed:latest",
            tmp_path / "out.sbd",
        )


def test_push_seed_oras_requires_existing_seed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "seedbraid.oci._require_oras_cli",
        lambda: "/usr/bin/oras",
    )
    with pytest.raises(ExternalToolError, match="Seed file not found"):
        push_seed_oras(
            tmp_path / "missing.sbd", "ghcr.io/acme/seedbraid-seed:latest"
        )


def test_readme_links_oci_integration_section() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    assert "### OCI Integration" in readme
    assert "examples/oci/README.md" in readme


def test_oci_example_documents_ghcr_ecr_gar_usage() -> None:
    oci_readme = (OCI_EXAMPLE_DIR / "README.md").read_text()
    assert "### GHCR" in oci_readme
    assert "### Amazon ECR" in oci_readme
    assert "### Google Artifact Registry (GAR)" in oci_readme
