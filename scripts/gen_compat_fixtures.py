from __future__ import annotations

import hashlib
import json
from pathlib import Path

from helix.container import OP_RAW, Recipe, RecipeOp, serialize_seed

FIXTURE_DIR = Path("tests/fixtures/compat/v1")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_fixture_bytes(
    *,
    payload: bytes,
    compression: str,
    signed: bool,
    signature_key: str | None = None,
    signature_key_id: str = "compat-fixture",
) -> bytes:
    chunk_hash = hashlib.sha256(payload).digest()
    manifest = {
        "format": "HLX1",
        "version": 1,
        "manifest_private": False,
        "source_size": len(payload),
        "source_sha256": _sha256_hex(payload),
        "chunker": {
            "name": "fixed",
            "min": len(payload),
            "avg": len(payload),
            "max": len(payload),
            "window_size": 16,
        },
        "portable": True,
        "learn": False,
        "stats": {
            "total_chunks": 1,
            "reused_chunks": 0,
            "new_chunks": 1,
            "raw_chunks": 1,
            "unique_hashes": 1,
        },
        "created_at": "2026-02-13T00:00:00+00:00",
        "fixture_name": "compat-v1",
    }
    recipe = Recipe(
        hash_table=[chunk_hash],
        ops=[RecipeOp(opcode=OP_RAW, hash_index=0)],
    )
    return serialize_seed(
        manifest=manifest,
        recipe=recipe,
        raw_payloads={0: payload},
        manifest_compression=compression,
        signature_key=signature_key if signed else None,
        signature_key_id=signature_key_id,
    )


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    specs = [
        {
            "filename": "portable_raw_v1.hlx",
            "payload": b"HELIX-COMPAT-FIXTURE-V1\nportable raw payload\n",
            "compression": "zlib",
            "signed": False,
        },
        {
            "filename": "portable_raw_signed_v1.hlx",
            "payload": (
                b"HELIX-COMPAT-FIXTURE-V1\nsigned portable raw payload\n"
            ),
            "compression": "none",
            "signed": True,
            "signature_key": "fixture-sign-key-v1",
            "signature_key_id": "compat-v1-sign",
        },
    ]

    metadata: list[dict[str, object]] = []
    for spec in specs:
        blob = _build_fixture_bytes(
            payload=spec["payload"],
            compression=spec["compression"],
            signed=bool(spec["signed"]),
            signature_key=spec.get("signature_key"),
            signature_key_id=str(
                spec.get("signature_key_id", "compat-fixture")
            ),
        )
        path = FIXTURE_DIR / str(spec["filename"])
        path.write_bytes(blob)
        metadata.append(
            {
                "filename": spec["filename"],
                "seed_sha256": _sha256_hex(blob),
                "decoded_sha256": _sha256_hex(spec["payload"]),
                "decoded_size": len(spec["payload"]),
                "compression": spec["compression"],
                "signed": spec["signed"],
                "signature_key": spec.get("signature_key"),
                "signature_key_id": spec.get("signature_key_id"),
            }
        )

    manifest_path = FIXTURE_DIR / "manifest.json"
    content = json.dumps({"fixtures": metadata}, indent=2, sort_keys=True)
    manifest_path.write_text(content + "\n")
    print(f"wrote {len(metadata)} fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
