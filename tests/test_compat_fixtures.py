from __future__ import annotations

import hashlib
import json
from pathlib import Path

from helix.codec import decode_file, verify_seed
from helix.container import read_seed, verify_signature

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "compat" / "v1"


def _load_manifest() -> list[dict]:
    blob = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    fixtures = blob.get("fixtures")
    assert isinstance(fixtures, list)
    return fixtures


def test_compat_fixture_hashes_are_frozen() -> None:
    for entry in _load_manifest():
        path = FIXTURE_DIR / str(entry["filename"])
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == entry["seed_sha256"], f"fixture digest drifted: {path.name}"


def test_compat_fixtures_parse_verify_and_decode(tmp_path: Path) -> None:
    genome = tmp_path / "genome"

    for entry in _load_manifest():
        seed_path = FIXTURE_DIR / str(entry["filename"])
        seed = read_seed(seed_path)

        assert seed.manifest["format"] == "HLX1"
        assert seed.manifest["version"] == 1
        assert seed.manifest["portable"] is True

        signature_key = entry.get("signature_key")
        if bool(entry["signed"]):
            assert signature_key is not None
            ok, reason = verify_signature(seed, str(signature_key))
            assert ok, reason
            report = verify_seed(
                seed_path,
                genome,
                strict=True,
                require_signature=True,
                signature_key=str(signature_key),
            )
        else:
            report = verify_seed(seed_path, genome, strict=True)
        assert report.ok

        out_path = tmp_path / f"{Path(str(entry['filename'])).stem}.decoded"
        digest = decode_file(seed_path, genome, out_path)
        assert digest == entry["decoded_sha256"]
        assert out_path.stat().st_size == int(entry["decoded_size"])
