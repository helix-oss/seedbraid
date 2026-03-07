"""ML platform integration hooks for seed metadata logging.

Supports MLflow experiment tracking and Hugging Face Hub uploads
with structured seed metadata sidecars.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .container import read_seed
from .errors import ExternalToolError


@dataclass(frozen=True)
class MLflowLogResult:
    experiment_id: str
    run_id: str


@dataclass(frozen=True)
class HuggingFaceUploadResult:
    repo_id: str
    repo_type: str
    revision: str
    seed_remote_path: str
    metadata_remote_path: str


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _stringify_metadata_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def build_seed_metadata(
    seed_path: str | Path,
    *,
    cid: str | None = None,
    oci_reference: str | None = None,
    encryption_key: str | None = None,
) -> dict[str, object]:
    """Build a metadata dict from a seed file.

    Extracts manifest fields and computes a SHA-256
    digest of the seed file.  Optionally includes
    IPFS CID and OCI reference.

    Args:
        seed_path: Path to the ``.hlx`` seed file.
        cid: IPFS CID to include in metadata.
        oci_reference: OCI reference to include.
        encryption_key: Passphrase to decrypt the
            seed if encrypted.

    Returns:
        Dict with keys such as ``"seed_file"``,
        ``"seed_sha256"``, ``"chunker"``,
        ``"source_sha256"``, and more.
    """
    seed_path = Path(seed_path)
    seed = read_seed(seed_path, encryption_key=encryption_key)
    manifest = seed.manifest

    chunker_name = "unknown"
    chunker = manifest.get("chunker")
    if isinstance(chunker, dict) and chunker.get("name"):
        chunker_name = str(chunker["name"])

    metadata: dict[str, object] = {
        "seed_file": seed_path.name,
        "seed_sha256": _sha256_file(seed_path),
        "seed_format": manifest.get("format"),
        "seed_version": manifest.get("version"),
        "source_sha256": manifest.get("source_sha256"),
        "source_size": manifest.get("source_size"),
        "chunker": chunker_name,
        "manifest_private": bool(manifest.get("manifest_private", False)),
        "portable": bool(manifest.get("portable", False)),
        "learn": bool(manifest.get("learn", False)),
    }
    if manifest.get("created_at") is not None:
        metadata["created_at"] = manifest.get("created_at")
    if cid is not None:
        metadata["ipfs_cid"] = cid
    if oci_reference is not None:
        metadata["oci_reference"] = oci_reference
    return metadata


def write_seed_metadata(
    metadata: dict[str, object],
    out_path: str | Path,
) -> Path:
    """Write seed metadata to a JSON sidecar file.

    Creates parent directories if needed.

    Args:
        metadata: Metadata dict as returned by
            ``build_seed_metadata``.
        out_path: Destination file path for the
            JSON sidecar.

    Returns:
        The ``out_path`` as a ``Path`` object.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(metadata, sort_keys=True, indent=2)
    out_path.write_text(text + "\n", encoding="utf-8")
    return out_path


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None,
    token: str | None,
    timeout_s: float,
    not_found_ok: bool = False,
) -> dict[str, Any] | None:
    body = (
        None
        if payload is None
        else json.dumps(
            payload, separators=(",", ":")
        ).encode("utf-8")
    )
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        url, data=body, headers=headers, method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        not_found = (
            exc.code in {400, 404}
            and "RESOURCE_DOES_NOT_EXIST" in detail
        )
        if not_found_ok and not_found:
            return None
        raise ExternalToolError(
            "MLflow API request failed"
            f" ({method} {url}):"
            f" HTTP {exc.code}. {detail}",
            code="HELIX_E_MLFLOW_REQUEST",
            next_action=(
                "Verify MLFLOW_TRACKING_URI/token,"
                " confirm server reachability,"
                " and retry the metadata"
                " logging command."
            ),
        ) from exc
    except urllib.error.URLError as exc:
        raise ExternalToolError(
            f"MLflow API request failed ({method} {url}): {exc}",
            code="HELIX_E_MLFLOW_REQUEST",
            next_action=(
                "Check network access to"
                " MLFLOW_TRACKING_URI and retry."
            ),
        ) from exc

    if not raw:
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalToolError(
            f"MLflow API returned invalid JSON for {method} {url}.",
            code="HELIX_E_MLFLOW_REQUEST",
            next_action="Inspect MLflow server/proxy response and retry.",
        ) from exc
    if not isinstance(decoded, dict):
        raise ExternalToolError(
            f"MLflow API response is not an object for {method} {url}.",
            code="HELIX_E_MLFLOW_REQUEST",
            next_action="Inspect MLflow server response and retry.",
        )
    return decoded


def _mlflow_params(metadata: dict[str, object]) -> list[dict[str, str]]:
    params: list[dict[str, str]] = []
    for key, value in sorted(metadata.items()):
        norm_key = key[:250]
        norm_value = _stringify_metadata_value(value)[:500]
        params.append({"key": norm_key, "value": norm_value})
    return params


def log_seed_metadata_to_mlflow(
    metadata: dict[str, object],
    *,
    tracking_uri: str,
    experiment_name: str,
    run_name: str,
    token: str | None = None,
    timeout_s: float = 20.0,
) -> MLflowLogResult:
    """Log seed metadata to MLflow as run parameters.

    Creates the experiment if it does not exist, then
    creates a new run and logs metadata as params.
    Parameter keys are truncated to 250 chars and
    values to 500 chars.

    Args:
        metadata: Metadata dict to log.
        tracking_uri: MLflow tracking server URL.
        experiment_name: Name of the MLflow
            experiment.
        run_name: Display name for the new run.
        token: Optional bearer token for
            authentication.
        timeout_s: HTTP request timeout in seconds.

    Returns:
        Result with ``experiment_id`` and
        ``run_id``.

    Raises:
        ExternalToolError: If the tracking URI is
            empty or API requests fail.
    """
    tracking_uri = tracking_uri.strip()
    if not tracking_uri:
        raise ExternalToolError(
            "MLflow tracking URI is required.",
            code="HELIX_E_MLFLOW_CONFIG",
            next_action="Pass --tracking-uri or set MLFLOW_TRACKING_URI.",
        )

    base_url = tracking_uri.rstrip("/")
    encoded_name = urllib.parse.quote(experiment_name, safe="")
    exp_resp = _request_json(
        "GET",
        f"{base_url}/api/2.0/mlflow/experiments"
        f"/get-by-name?experiment_name={encoded_name}",
        payload=None,
        token=token,
        timeout_s=timeout_s,
        not_found_ok=True,
    )

    experiment_id: str | None = None
    if exp_resp is not None and isinstance(exp_resp.get("experiment"), dict):
        exp = exp_resp["experiment"]
        exp_id = exp.get("experiment_id")
        if exp_id is not None:
            experiment_id = str(exp_id)

    if experiment_id is None:
        create_exp_resp = _request_json(
            "POST",
            f"{base_url}/api/2.0/mlflow/experiments/create",
            payload={"name": experiment_name},
            token=token,
            timeout_s=timeout_s,
        )
        if (
            create_exp_resp is None
            or create_exp_resp.get("experiment_id") is None
        ):
            raise ExternalToolError(
                "MLflow did not return"
                " experiment_id when creating"
                " experiment.",
                code="HELIX_E_MLFLOW_REQUEST",
                next_action="Check MLflow server logs and retry.",
            )
        experiment_id = str(create_exp_resp["experiment_id"])

    run_resp = _request_json(
        "POST",
        f"{base_url}/api/2.0/mlflow/runs/create",
        payload={"experiment_id": experiment_id, "run_name": run_name},
        token=token,
        timeout_s=timeout_s,
    )
    run_id: str | None = None
    if run_resp is not None and isinstance(run_resp.get("run"), dict):
        run = run_resp["run"]
        if (
            isinstance(run.get("info"), dict)
            and run["info"].get("run_id") is not None
        ):
            run_id = str(run["info"]["run_id"])
    if run_id is None:
        raise ExternalToolError(
            "MLflow did not return run_id when creating run.",
            code="HELIX_E_MLFLOW_REQUEST",
            next_action="Check MLflow server logs and retry.",
        )

    _request_json(
        "POST",
        f"{base_url}/api/2.0/mlflow/runs/log-batch",
        payload={
            "run_id": run_id,
            "params": _mlflow_params(metadata),
            "tags": [
                {"key": "helix.seed.metadata", "value": "true"},
                {"key": "helix.seed.schema", "value": "v1"},
            ],
        },
        token=token,
        timeout_s=timeout_s,
    )

    return MLflowLogResult(experiment_id=experiment_id, run_id=run_id)


def _resolve_hf_cli() -> list[str]:
    hf_cli = shutil.which("huggingface-cli")
    if hf_cli:
        return [hf_cli, "upload"]
    hf_modern = shutil.which("hf")
    if hf_modern:
        return [hf_modern, "upload"]
    raise ExternalToolError(
        "Hugging Face CLI not found. Install `huggingface_hub` CLI and "
        "ensure `huggingface-cli` or `hf` is on PATH.",
        code="HELIX_E_HF_CONFIG",
        next_action=(
            "Install Hugging Face CLI and verify"
            " with `huggingface-cli --help`."
        ),
    )


def upload_seed_and_metadata_to_hf(
    *,
    repo_id: str,
    seed_path: str | Path,
    metadata_path: str | Path,
    repo_type: str = "dataset",
    revision: str = "main",
    remote_prefix: str = "helix/seeds",
    token: str | None = None,
) -> HuggingFaceUploadResult:
    """Upload a seed and its metadata sidecar to HF Hub.

    Uses ``huggingface-cli`` (or ``hf``) to upload
    both files.  Token is resolved from the argument,
    ``HF_TOKEN``, ``HUGGINGFACE_HUB_TOKEN``, or
    ``HUGGINGFACEHUB_API_TOKEN`` environment
    variables in that order.

    Args:
        repo_id: Hugging Face repository identifier
            (e.g. ``"user/repo"``).
        seed_path: Path to the ``.hlx`` seed file.
        metadata_path: Path to the JSON sidecar.
        repo_type: One of ``"dataset"``,
            ``"model"``, ``"space"``.
        revision: Git revision / branch to upload
            to.
        remote_prefix: Remote directory prefix for
            uploaded files.
        token: Hugging Face API token.

    Returns:
        Result with repo info and remote file paths.

    Raises:
        ExternalToolError: If the CLI is missing,
            files do not exist, token is missing,
            or the upload fails.
    """
    if repo_type not in {"dataset", "model", "space"}:
        raise ExternalToolError(
            f"Unsupported Hugging Face repo type: {repo_type}",
            code="HELIX_E_HF_CONFIG",
            next_action="Use --repo-type dataset, model, or space.",
        )

    seed_path = Path(seed_path)
    metadata_path = Path(metadata_path)
    if not seed_path.exists():
        raise ExternalToolError(
            f"Seed file not found: {seed_path}",
            code="HELIX_E_SEED_NOT_FOUND",
            next_action="Provide an existing `.hlx` seed file path.",
        )
    if not metadata_path.exists():
        raise ExternalToolError(
            f"Metadata sidecar not found: {metadata_path}",
            code="HELIX_E_HF_CONFIG",
            next_action="Generate metadata sidecar before upload.",
        )

    resolved_token = (
        token
        or os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
    )
    if not resolved_token:
        raise ExternalToolError(
            "Hugging Face token is required for upload.",
            code="HELIX_E_HF_CONFIG",
            next_action="Set HF_TOKEN (or pass --token) and retry.",
        )

    base_cmd = _resolve_hf_cli()
    prefix = remote_prefix.strip("/")
    seed_remote = f"{prefix}/{seed_path.name}" if prefix else seed_path.name
    metadata_remote = (
        f"{prefix}/{metadata_path.name}"
        if prefix
        else metadata_path.name
    )

    env = os.environ.copy()
    env["HF_TOKEN"] = resolved_token
    env.setdefault("HUGGINGFACE_HUB_TOKEN", resolved_token)

    uploads = (
        (seed_path, seed_remote),
        (metadata_path, metadata_remote),
    )
    for local_path, remote_path in uploads:
        cmd = [
            *base_cmd,
            repo_id,
            str(local_path),
            remote_path,
            "--repo-type",
            repo_type,
            "--revision",
            revision,
        ]
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if proc.returncode != 0:
            detail = (
                proc.stderr.strip()
                or proc.stdout.strip()
                or "hf upload failed"
            )
            raise ExternalToolError(
                f"Hugging Face upload failed for {local_path.name}: {detail}",
                code="HELIX_E_HF_REQUEST",
                next_action=(
                    "Verify repo permissions/token"
                    " scope and repository path,"
                    " then retry upload."
                ),
            )

    return HuggingFaceUploadResult(
        repo_id=repo_id,
        repo_type=repo_type,
        revision=revision,
        seed_remote_path=seed_remote,
        metadata_remote_path=metadata_remote,
    )
