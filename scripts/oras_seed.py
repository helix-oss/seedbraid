from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from helix.errors import HelixError
from helix.oci import (
    HELIX_OCI_ARTIFACT_TYPE,
    HELIX_OCI_SEED_MEDIA_TYPE,
    pull_seed_oras,
    push_seed_oras,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push/pull Helix seed files via OCI registries using ORAS."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    push = sub.add_parser("push", help="Push a .hlx seed to OCI reference")
    push.add_argument("seed", type=Path, help="Path to .hlx seed file")
    push.add_argument("reference", help="OCI reference: <registry>/<repo>:<tag>")
    push.add_argument(
        "--artifact-type",
        default=HELIX_OCI_ARTIFACT_TYPE,
        help="OCI artifact type for Helix seeds.",
    )
    push.add_argument(
        "--media-type",
        default=HELIX_OCI_SEED_MEDIA_TYPE,
        help="Layer media type for Helix seed payload.",
    )
    push.add_argument(
        "--encryption-key",
        default=None,
        help="Passphrase when reading encrypted HLE1 seed for annotation extraction.",
    )

    pull = sub.add_parser("pull", help="Pull a .hlx seed from OCI reference")
    pull.add_argument("reference", help="OCI reference: <registry>/<repo>:<tag>")
    pull.add_argument("out", type=Path, help="Output path for pulled .hlx seed")

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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "push":
            annotations = push_seed_oras(
                args.seed,
                args.reference,
                artifact_type=args.artifact_type,
                media_type=args.media_type,
                encryption_key=args.encryption_key or os.environ.get("HELIX_ENCRYPTION_KEY"),
            )
            print(
                "pushed "
                f"seed={Path(args.seed).name} ref={args.reference} "
                f"artifact_type={args.artifact_type} media_type={args.media_type}"
            )
            for key, value in sorted(annotations.items()):
                print(f"annotation {key}={value}")
            return 0

        pull_seed_oras(args.reference, args.out)
        print(f"pulled ref={args.reference} out={args.out}")
        return 0
    except Exception as exc:  # noqa: BLE001
        return _print_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
