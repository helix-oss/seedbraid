from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from helix.errors import HelixError
from helix.mlhooks import (
    build_seed_metadata,
    log_seed_metadata_to_mlflow,
    upload_seed_and_metadata_to_hf,
    write_seed_metadata,
)


def _default_metadata_path(seed_path: Path) -> Path:
    return seed_path.with_name(f"{seed_path.name}.metadata.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helix ML tooling hooks (MLflow / Hugging Face)")
    sub = parser.add_subparsers(dest="command", required=True)

    mlflow = sub.add_parser("mlflow-log", help="Log Helix seed metadata to MLflow")
    mlflow.add_argument("seed", type=Path, help="Path to .hlx seed")
    mlflow.add_argument("--tracking-uri", default=None, help="MLflow tracking URI")
    mlflow.add_argument(
        "--experiment",
        default=os.environ.get("HELIX_MLFLOW_EXPERIMENT", "helix-seeds"),
        help="MLflow experiment name",
    )
    mlflow.add_argument(
        "--run-name",
        default=None,
        help="MLflow run name (default: seed filename)",
    )
    mlflow.add_argument("--token", default=None, help="MLflow API token")
    mlflow.add_argument("--timeout-s", type=float, default=20.0, help="HTTP timeout seconds")
    mlflow.add_argument("--metadata-out", type=Path, default=None, help="Metadata sidecar output")
    mlflow.add_argument("--cid", default=None, help="Optional IPFS CID")
    mlflow.add_argument("--oci-reference", default=None, help="Optional OCI reference")
    mlflow.add_argument(
        "--encryption-key",
        default=None,
        help="Passphrase for encrypted HLE1 seeds (or use HELIX_ENCRYPTION_KEY)",
    )

    hf = sub.add_parser("hf-upload", help="Upload seed + metadata sidecar to Hugging Face Hub")
    hf.add_argument("seed", type=Path, help="Path to .hlx seed")
    hf.add_argument("repo_id", help="Hugging Face repo id")
    hf.add_argument("--repo-type", default="dataset", help="dataset | model | space")
    hf.add_argument("--revision", default="main", help="Target revision")
    hf.add_argument("--remote-prefix", default="helix/seeds", help="Remote folder prefix")
    hf.add_argument("--token", default=None, help="Hugging Face token")
    hf.add_argument("--metadata", type=Path, default=None, help="Existing metadata sidecar path")
    hf.add_argument(
        "--metadata-out",
        type=Path,
        default=None,
        help="Generated metadata sidecar path",
    )
    hf.add_argument("--cid", default=None, help="Optional IPFS CID")
    hf.add_argument("--oci-reference", default=None, help="Optional OCI reference")
    hf.add_argument(
        "--encryption-key",
        default=None,
        help="Passphrase for encrypted HLE1 seeds (or use HELIX_ENCRYPTION_KEY)",
    )

    return parser


def _print_error(exc: Exception) -> int:
    if isinstance(exc, HelixError):
        info = exc.as_info()
        print(f"error[{info.code}]: {info.message}", file=sys.stderr)
        if info.next_action:
            print(f"next_action: {info.next_action}", file=sys.stderr)
        return 1
    print(f"error[HELIX_E_UNKNOWN]: {exc}", file=sys.stderr)
    return 1


def _build_and_write_metadata(args) -> tuple[dict[str, object], Path]:  # noqa: ANN001
    encryption_key = args.encryption_key or os.environ.get("HELIX_ENCRYPTION_KEY")
    metadata = build_seed_metadata(
        args.seed,
        cid=args.cid,
        oci_reference=args.oci_reference,
        encryption_key=encryption_key,
    )

    metadata_out = args.metadata_out or _default_metadata_path(args.seed)
    write_seed_metadata(metadata, metadata_out)
    return metadata, metadata_out


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "mlflow-log":
            tracking_uri = args.tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
            if not tracking_uri:
                raise HelixError(
                    "MLflow tracking URI is required.",
                    code="HELIX_E_MLFLOW_CONFIG",
                    next_action="Pass --tracking-uri or set MLFLOW_TRACKING_URI.",
                )

            metadata, metadata_path = _build_and_write_metadata(args)
            run_name = args.run_name or args.seed.name
            token = args.token or os.environ.get("MLFLOW_TRACKING_TOKEN")
            result = log_seed_metadata_to_mlflow(
                metadata,
                tracking_uri=tracking_uri,
                experiment_name=args.experiment,
                run_name=run_name,
                token=token,
                timeout_s=args.timeout_s,
            )
            print(
                "mlflow_logged "
                f"experiment_id={result.experiment_id} run_id={result.run_id} "
                f"metadata={metadata_path}"
            )
            return 0

        if args.metadata is not None:
            metadata_path = args.metadata
        else:
            _, metadata_path = _build_and_write_metadata(args)

        result = upload_seed_and_metadata_to_hf(
            repo_id=args.repo_id,
            seed_path=args.seed,
            metadata_path=metadata_path,
            repo_type=args.repo_type,
            revision=args.revision,
            remote_prefix=args.remote_prefix,
            token=args.token,
        )
        print(
            "hf_uploaded "
            f"repo={result.repo_id} repo_type={result.repo_type} revision={result.revision} "
            f"seed_remote={result.seed_remote_path} metadata_remote={result.metadata_remote_path}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        return _print_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
