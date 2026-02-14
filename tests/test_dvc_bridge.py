from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DVC_EXAMPLE_DIR = REPO_ROOT / "examples" / "dvc"
DVC_SCRIPTS_DIR = DVC_EXAMPLE_DIR / "scripts"


def _write_fake_helix(tmp_path: Path, body: str) -> Path:
    fake = tmp_path / "fake_helix.sh"
    fake.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body)
    fake.chmod(0o755)
    return fake


def test_dvc_pipeline_declares_encode_verify_fetch_stages() -> None:
    pipeline = (DVC_EXAMPLE_DIR / "dvc.yaml").read_text()

    assert "encode:" in pipeline
    assert "verify:" in pipeline
    assert "fetch:" in pipeline
    assert "cmd: ./scripts/encode_seed.sh" in pipeline
    assert "cmd: ./scripts/verify_seed.sh" in pipeline
    assert "cmd: ./scripts/fetch_seed.sh" in pipeline


def test_readme_links_dvc_integration_section() -> None:
    root_readme = (REPO_ROOT / "README.md").read_text()
    assert "## DVC Integration (HLX-ECO-003)" in root_readme
    assert "examples/dvc/README.md" in root_readme


def test_dvc_example_documents_artifact_layout() -> None:
    dvc_readme = (DVC_EXAMPLE_DIR / "README.md").read_text()
    assert "Recommended Artifact Layout" in dvc_readme
    assert "artifacts/seed/current.hlx" in dvc_readme
    assert "artifacts/genome/snapshot.hgs" in dvc_readme
    assert "artifacts/metadata/seed.cid" in dvc_readme


def test_dvc_verify_script_uses_strict_mode() -> None:
    verify_script = (DVC_SCRIPTS_DIR / "verify_seed.sh").read_text()
    assert "verify" in verify_script
    assert "--strict" in verify_script


def test_dvc_verify_script_failure_propagates(tmp_path: Path) -> None:
    fake_helix = _write_fake_helix(
        tmp_path,
        """
if [[ "$1" == "verify" ]]; then
  echo "verify failed: forced mismatch" >&2
  exit 1
fi
exit 0
""",
    )

    seed_path = tmp_path / "seed.hlx"
    seed_path.write_bytes(b"HLX1" + b"x" * 64)
    genome_path = tmp_path / "genome"
    genome_path.mkdir()
    verify_ok_path = tmp_path / "verify.ok"

    env = os.environ.copy()
    env.update(
        {
            "HELIX_DVC_HELIX_BIN": str(fake_helix),
            "HELIX_DVC_SEED_PATH": str(seed_path),
            "HELIX_DVC_GENOME_PATH": str(genome_path),
            "HELIX_DVC_VERIFY_OK_PATH": str(verify_ok_path),
        }
    )

    result = subprocess.run(
        ["bash", str(DVC_SCRIPTS_DIR / "verify_seed.sh")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "forced mismatch" in result.stderr
    assert not verify_ok_path.exists()


def test_dvc_fetch_script_bootstraps_cid_and_fetches(tmp_path: Path) -> None:
    fake_helix = _write_fake_helix(
        tmp_path,
        """
if [[ "$1" == "publish" ]]; then
  echo "bafyfakecid"
  exit 0
fi

if [[ "$1" == "fetch" ]]; then
  if [[ "$2" != "bafyfakecid" ]]; then
    echo "unexpected cid: $2" >&2
    exit 2
  fi

  out_path=""
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--out" ]]; then
      shift
      out_path="$1"
      break
    fi
    shift
  done

  if [[ -z "$out_path" ]]; then
    echo "missing --out" >&2
    exit 3
  fi

  mkdir -p "$(dirname "$out_path")"
  printf 'HLX1fetched' > "$out_path"
  exit 0
fi

exit 0
""",
    )

    seed_path = tmp_path / "seed.hlx"
    seed_path.write_bytes(b"HLX1" + b"z" * 32)
    cid_path = tmp_path / "seed.cid"
    fetched_path = tmp_path / "fetched.hlx"

    env = os.environ.copy()
    env.update(
        {
            "HELIX_DVC_HELIX_BIN": str(fake_helix),
            "HELIX_DVC_SEED_PATH": str(seed_path),
            "HELIX_DVC_CID_PATH": str(cid_path),
            "HELIX_DVC_FETCHED_PATH": str(fetched_path),
        }
    )

    result = subprocess.run(
        ["bash", str(DVC_SCRIPTS_DIR / "fetch_seed.sh")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert cid_path.read_text().strip() == "bafyfakecid"
    assert fetched_path.read_bytes() == b"HLX1fetched"
