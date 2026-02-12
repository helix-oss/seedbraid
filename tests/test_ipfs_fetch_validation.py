from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from helix.container import OP_RAW, Recipe, RecipeOp, encrypt_seed_bytes, serialize_seed
from helix.errors import ExternalToolError
from helix.ipfs import fetch_seed


@dataclass
class _Proc:
    returncode: int
    stdout: bytes
    stderr: bytes


def _minimal_seed_bytes() -> bytes:
    manifest = {
        "format": "HLX1",
        "version": 1,
        "manifest_private": True,
        "source_size": None,
        "source_sha256": None,
        "chunker": {"name": "fixed"},
        "portable": True,
        "learn": True,
    }
    recipe = Recipe(hash_table=[b"\x00" * 32], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)])
    return serialize_seed(manifest, recipe, {0: b"abc"}, manifest_compression="zlib")


def test_fetch_accepts_encrypted_seed_without_key(tmp_path: Path, monkeypatch) -> None:
    encrypted = encrypt_seed_bytes(_minimal_seed_bytes(), "fetch-key")
    out = tmp_path / "fetched.hlx"

    monkeypatch.setattr("helix.ipfs.shutil.which", lambda _name: "/usr/bin/ipfs")
    monkeypatch.setattr(
        "helix.ipfs.subprocess.run",
        lambda *_args, **_kwargs: _Proc(returncode=0, stdout=encrypted, stderr=b""),
    )

    fetch_seed("bafy-test-cid", out)
    assert out.read_bytes() == encrypted


def test_fetch_rejects_malformed_encrypted_seed(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "fetched.hlx"
    malformed = b"HLE1" + b"\x00" * 8

    monkeypatch.setattr("helix.ipfs.shutil.which", lambda _name: "/usr/bin/ipfs")
    monkeypatch.setattr(
        "helix.ipfs.subprocess.run",
        lambda *_args, **_kwargs: _Proc(returncode=0, stdout=malformed, stderr=b""),
    )

    with pytest.raises(ExternalToolError, match="integrity/manifest validation failed"):
        fetch_seed("bafy-test-cid", out)
