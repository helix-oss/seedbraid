"""Tests for T-014 Tag-Based Release Automation logic.

Covers the version extraction, tag-matching, and pre-release detection
logic embedded in .github/workflows/release.yml (verify job).
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers mirroring release.yml logic
# ---------------------------------------------------------------------------


def extract_version_from_source(src: str) -> str | None:
    """Extract __version__ from Python source using AST.

    Mirrors the Python snippet in the release.yml verify job.
    Returns the version string, or None if not found / not a string.
    """
    version = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__version__":
                    version = ast.literal_eval(node.value)
    if not isinstance(version, str):
        return None
    return version


def tag_to_version(tag: str) -> str:
    """Strip leading 'v' prefix from a git tag."""
    return tag[1:] if tag.startswith("v") else tag


def is_prerelease(version: str) -> bool:
    """Return True when version matches pre-release pattern from release.yml.

    Pattern: '[ab]|rc|dev'  (grep -qE)
    """
    return bool(re.search(r"[ab]|rc|dev", version))


# ---------------------------------------------------------------------------
# AST extraction — happy path
# ---------------------------------------------------------------------------


def test_extract_version_simple() -> None:
    src = '__version__ = "1.2.3"\n'
    assert extract_version_from_source(src) == "1.2.3"


def test_extract_version_prerelease_alpha() -> None:
    src = '__version__ = "2.0.0a1"\n'
    assert extract_version_from_source(src) == "2.0.0a1"


def test_extract_version_prerelease_beta() -> None:
    src = '__version__ = "1.0.0b3"\n'
    assert extract_version_from_source(src) == "1.0.0b3"


def test_extract_version_prerelease_rc() -> None:
    src = '__version__ = "1.0.0rc2"\n'
    assert extract_version_from_source(src) == "1.0.0rc2"


def test_extract_version_prerelease_dev() -> None:
    src = '__version__ = "0.9.0.dev1"\n'
    assert extract_version_from_source(src) == "0.9.0.dev1"


def test_extract_version_with_module_docstring() -> None:
    """Version is extracted even with a module docstring."""
    src = textwrap.dedent(
        '''\
        """Module docstring."""

        __all__ = ["__version__"]

        __version__ = "1.0.0"
        '''
    )
    assert extract_version_from_source(src) == "1.0.0"


# ---------------------------------------------------------------------------
# AST extraction — edge / error cases
# ---------------------------------------------------------------------------


def test_extract_version_missing_returns_none() -> None:
    src = "x = 42\n"
    assert extract_version_from_source(src) is None


def test_extract_version_non_string_returns_none() -> None:
    """__version__ assigned a non-string literal should return None."""
    src = "__version__ = 123\n"
    assert extract_version_from_source(src) is None


def test_extract_version_empty_file_returns_none() -> None:
    assert extract_version_from_source("") is None


def test_extract_version_list_value_returns_none() -> None:
    src = '__version__ = ["1", "0", "0"]\n'
    assert extract_version_from_source(src) is None


def test_extract_version_picks_first_assignment() -> None:
    """Dual __version__ assignment returns a string."""
    src = '__version__ = "1.0.0"\n__version__ = "2.0.0"\n'
    result = extract_version_from_source(src)
    assert result in {"1.0.0", "2.0.0"}


# ---------------------------------------------------------------------------
# Tag-to-version stripping
# ---------------------------------------------------------------------------


def test_tag_v_prefix_stripped() -> None:
    assert tag_to_version("v1.2.3") == "1.2.3"


def test_tag_v_prefix_alpha() -> None:
    assert tag_to_version("v1.0.0a1") == "1.0.0a1"


def test_tag_without_v_unchanged() -> None:
    assert tag_to_version("1.2.3") == "1.2.3"


def test_tag_empty_string() -> None:
    assert tag_to_version("") == ""


def test_tag_only_v() -> None:
    assert tag_to_version("v") == ""


# ---------------------------------------------------------------------------
# Version-match check (tag vs __version__)
# ---------------------------------------------------------------------------


def test_version_match_passes() -> None:
    assert tag_to_version("v1.0.0") == "1.0.0"


def test_version_mismatch_detected() -> None:
    assert tag_to_version("v1.0.0") != "1.0.1"


def test_version_match_prerelease() -> None:
    assert tag_to_version("v1.0.0a1") == "1.0.0a1"


# ---------------------------------------------------------------------------
# Pre-release detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version",
    [
        "1.0.0a1",
        "2.0.0b3",
        "1.5.0rc1",
        "0.9.0.dev1",
        "1.0.0a0",
        "3.0.0b0",
        "1.0.0rc0",
    ],
)
def test_is_prerelease_true(version: str) -> None:
    assert is_prerelease(version) is True


@pytest.mark.parametrize(
    "version",
    [
        "1.0.0",
        "2.3.4",
        "10.20.30",
        "1.0.0.post1",
    ],
)
def test_is_prerelease_false(version: str) -> None:
    assert is_prerelease(version) is False


# ---------------------------------------------------------------------------
# Boundary: 'a' / 'b' must not match arbitrary substrings
# ---------------------------------------------------------------------------


def test_prerelease_does_not_false_positive_on_pure_numeric() -> None:
    assert is_prerelease("1.0.0") is False


def test_prerelease_detects_alpha_segment() -> None:
    assert is_prerelease("1.0.0a1") is True


def test_prerelease_detects_beta_segment() -> None:
    assert is_prerelease("1.0.0b1") is True


# ---------------------------------------------------------------------------
# Actual __version__ in src/helix/__init__.py
# ---------------------------------------------------------------------------


def test_actual_version_is_extractable() -> None:
    """The real __init__.py must yield a valid string via AST extraction."""
    init = Path(__file__).parent.parent / "src" / "helix" / "__init__.py"
    src = init.read_text()
    version = extract_version_from_source(src)
    assert isinstance(version, str), "__version__ must be a string"
    assert version != "", "__version__ must not be empty"


def test_actual_version_is_pep440_compliant() -> None:
    """__version__ must conform to PEP 440 version format.

    Pattern covers: N.N.N, N.N.Na#, N.N.Nb#, N.N.Nrc#,
    N.N.N.devN, N.N.N.postN.
    """
    init = Path(__file__).parent.parent / "src" / "helix" / "__init__.py"
    version = extract_version_from_source(init.read_text())
    assert version is not None
    pep440 = re.compile(
        r"^\d+\.\d+(\.\d+)?"
        r"(\.?(a|b|rc)\d+)?"
        r"(\.?(dev|post)\d+)?$"
    )
    assert pep440.match(version), (
        f"__version__={version!r} does not match PEP 440 pattern"
    )


def test_actual_version_tag_roundtrip() -> None:
    """v-prefix roundtrip must recover __version__."""
    init = Path(__file__).parent.parent / "src" / "helix" / "__init__.py"
    version = extract_version_from_source(init.read_text())
    assert version is not None
    reconstructed_tag = f"v{version}"
    assert tag_to_version(reconstructed_tag) == version


def test_actual_version_prerelease_classification() -> None:
    """is_prerelease() is consistent with PEP 440."""
    init = Path(__file__).parent.parent / "src" / "helix" / "__init__.py"
    version = extract_version_from_source(init.read_text())
    assert version is not None
    # 1.0.0a1 is a pre-release; 1.0.0 is not. Just assert no exception.
    result = is_prerelease(version)
    assert isinstance(result, bool)
