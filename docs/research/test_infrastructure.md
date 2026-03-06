# Helix Test Infrastructure Survey

**Date**: 2026-03-06  
**Scope**: Comprehensive analysis of test files, fixtures, patterns, and configuration

---

## Executive Summary

The Helix project maintains a mature pytest-based test infrastructure with **23 test files** (1,768 total lines), **61+ test functions**, and **3 committed compatibility fixtures**. Testing patterns include CLI integration (CliRunner), mocking (monkeypatch), temporary file systems (tmp_path), subprocess spawning, and graceful IPFS availability detection. Configuration is minimal (pyproject.toml) with auto-coverage reporting and a 75% CI threshold.

---

## Test File Inventory

### By Module Coverage (23 files)

| Module | Test File | Focus |
|--------|-----------|-------|
| **Core Codec** | test_chunking.py | CDC determinism (buzhash, rabin) |
| | test_container.py | HLX1 serialization, integrity checks |
| | test_roundtrip.py | Full encode/decode cycles |
| | test_encryption.py | Encryption key requirements, decryption flows |
| **Verification** | test_prime_verify.py | Priming and verification |
| | test_verify_strict.py | Strict mode verification |
| | test_signature.py | Signature generation/validation |
| **Genome/Storage** | test_genes_pack.py | Gene packing |
| | test_genome_snapshot.py | Snapshot operations |
| **IPFS Integration** | test_ipfs_optional.py | Conditional IPFS availability |
| | test_ipfs_fetch_validation.py | Fetch validation |
| | test_ipfs_reliability.py | Reliability/retry logic |
| | test_publish_warning.py | Publish-side behaviors |
| | test_remote_pinning.py | Remote pinning API integration |
| **Ecosystem Bridges** | test_dvc_bridge.py | DVC pipeline integration (8 tests) |
| | test_oci_oras_bridge.py | OCI/ORAS container bridge (6 tests) |
| | test_ml_hooks.py | MLflow, HuggingFace upload hooks (6 tests) |
| **CLI & Tools** | test_keygen_cli.py | Encryption key generation (4 tests) |
| | test_doctor.py | Health check commands (4 tests) |
| **Diagnostics** | test_perf_gates.py | Performance benchmarks (2 tests) |
| | test_manifest_private.py | Manifest privacy flags (1 test) |
| **Compatibility** | test_compat_fixtures.py | Version-gated fixture tests (2 tests) |

---

## Configuration & Entry Points

### pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
addopts = "-q --cov=helix --cov-report=term-missing"
testpaths = ["tests"]
```

- **Default flags**: Quiet mode, auto-coverage collection, line-by-line coverage report
- **Coverage threshold**: 75% (enforced in CI via `scripts/bench_gate.py`)
- **Target**: `helix` package only (src/helix/)

### Run Commands

```bash
# Full test suite
PYTHONPATH=src uv run --no-editable python -m pytest

# Single file
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_<name>.py

# With coverage detail
pytest --cov=helix --cov-report=html

# Performance gate check
PYTHONPATH=src uv run python scripts/bench_gate.py
```

---

## Shared Fixtures & Test Utilities

### Key Fixture Pattern

**No central conftest.py exists.** Instead, fixtures are:

1. **pytest built-ins**: `tmp_path`, `monkeypatch` (used universally)
2. **Local creation**: Each test creates its own `Recipe`, manifest dicts, seed blobs
3. **File-based**: Compatibility fixtures stored in `tests/fixtures/compat/v1/`

### Compatibility Fixtures

**Path**: `tests/fixtures/compat/v1/`

| File | Purpose | Validation |
|------|---------|-----------|
| `manifest.json` | Index of fixture metadata (filename, sha256, decoded_sha256, signed, signature_key) |  Loaded in test_compat_fixtures.py |
| `portable_raw_v1.hlx` | Basic HLX1 seed (unsigned, portable) | Parsed, verified, decoded |
| `portable_raw_signed_v1.hlx` | HLX1 seed with signature | Signature verification required |

**Fixture regeneration command**:
```bash
PYTHONPATH=src uv run python scripts/gen_compat_fixtures.py
```

---

## Testing Patterns & Conventions

### 1. CLI Testing (CliRunner)

**Pattern**: Typer's `CliRunner` for command invocation

```python
from typer.testing import CliRunner
from helix.cli import app

def test_gen_encryption_key_prints_token(monkeypatch) -> None:
    monkeypatch.setattr("helix.cli.secrets.token_urlsafe", lambda _n: "generated-token")
    runner = CliRunner()
    result = runner.invoke(app, ["gen-encryption-key"])
    assert result.exit_code == 0
    assert result.output.strip() == "generated-token"
```

**Files using CliRunner**:
- test_keygen_cli.py (4 tests) — token generation, shell output, validation
- test_remote_pinning.py (1 test) — pin remote-add with error reporting
- test_doctor.py (implied, 4 tests) — health checks

### 2. Mocking (monkeypatch)

**Pattern**: Replace internal functions, environment variables, external tools

```python
# Function mocking
monkeypatch.setattr("helix.cli.secrets.token_urlsafe", lambda _n: "token")

# Environment variables
monkeypatch.delenv("HF_TOKEN", raising=False)
monkeypatch.setenv("IPFS_PATH", str(ipfs_repo))

# Module-level functions
monkeypatch.setattr("helix.pinning.urllib.request.urlopen", _fake_urlopen)
monkeypatch.setattr("helix.mlhooks.subprocess.run", _fake_run)
```

**Typical patterns in**:
- test_remote_pinning.py — HTTP API mocking with retry simulation
- test_ml_hooks.py — MLflow _request_json, HF CLI subprocess mocks
- test_dvc_bridge.py — Fake helix binary simulation via subprocess

### 3. Temporary Filesystem (tmp_path)

**Pattern**: pytest's tmp_path fixture for file I/O

```python
def test_encrypted_seed_roundtrip_requires_key(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    seed = tmp_path / "seed.hlx"
    genome = tmp_path / "genome"
    
    src.write_bytes((b"encrypted-seed" * 4000) + bytes(range(128)))
    # ... encode/decode operations
    assert out.read_bytes() == src.read_bytes()
```

**Common patterns**:
- Create source files, genomes, seed outputs in tmp_path
- Write test data with controlled content
- Verify file existence and content equality

### 4. Exception Testing

**Pattern**: `pytest.raises()` for error path validation

```python
with pytest.raises(SeedFormatError, match="Encrypted seed requires decryption key"):
    decode_file(seed, genome, out)

with pytest.raises(ExternalToolError) as exc_info:
    provider.remote_add("bafy-test", retries=1)
assert exc_info.value.code == "HELIX_E_REMOTE_PIN_AUTH"
```

**Used for**:
- Encryption key requirement checks
- Manifest integrity validation
- External tool configuration errors

### 5. Conditional Test Skipping (IPFS Availability)

**Pattern**: Graceful skip when optional dependency unavailable

```python
import shutil
import subprocess
import pytest

def test_publish_fetch_if_ipfs_installed(tmp_path: Path, monkeypatch) -> None:
    if shutil.which("ipfs") is None:
        pytest.skip("ipfs CLI not installed")
    
    ipfs_repo = tmp_path / "ipfs-repo"
    monkeypatch.setenv("IPFS_PATH", str(ipfs_repo))
    init = subprocess.run(["ipfs", "init"], check=False, capture_output=True, text=True)
    if init.returncode != 0:
        pytest.skip(f"ipfs init failed: {init.stderr.strip()}")
    
    # ... test continues
```

**Files with IPFS skipping**:
- test_ipfs_optional.py — Main IPFS availability check
- test_ipfs_reliability.py — Retry/timeout scenarios (4 tests)
- test_ipfs_fetch_validation.py — Fetch validation with CID handling

### 6. Subprocess & External Tool Mocking

**Pattern**: Mock subprocess.run for external commands

```python
def _fake_run(cmd, check=False, text=True, capture_output=True, env=None):
    calls.append((cmd, None if env is None else env.get("HF_TOKEN")))
    return _Proc(returncode=0, stdout="ok", stderr="")

monkeypatch.setattr("helix.mlhooks.subprocess.run", _fake_run)

# Invoke CLI that spawns subprocess
result = upload_seed_and_metadata_to_hf(
    repo_id="acme/helix-seeds",
    seed_path=seed_path,
    token="hf-token",
)
```

**Used in**:
- test_dvc_bridge.py — Fake helix binary for script testing
- test_ml_hooks.py — HuggingFace CLI invocation
- test_oci_oras_bridge.py — ORAS container tool interaction

### 7. Data Fixtures via Local Creation

**Pattern**: Build test data programmatically (no large committed binaries)

```python
from helix.container import Recipe, RecipeOp, serialize_seed

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
```

**Used in**:
- test_container.py — Manifest, recipe, integrity tests
- test_ml_hooks.py — Metadata building and logging
- test_encryption.py — Encrypted seed roundtrips

---

## Test Markers & Grouping

### Known Test Markers

**No explicit pytest.mark decorators found** (search returned 0 matches).

Instead, organization is by:
- **File naming**: test_*.py for test discovery
- **Function naming**: test_* for function discovery
- **Tags/categories**: Implicit in file organization (e.g., test_ipfs_*.py, test_*_cli.py)

### Implicit Categories

1. **Core functionality**: test_chunking, test_container, test_encryption
2. **Integration**: test_ipfs_*, test_dvc_*, test_oci_*, test_ml_*, test_remote_*
3. **Security/Verification**: test_signature, test_verify_strict, test_manifest_private
4. **CLI & Tools**: test_*_cli, test_keygen_cli, test_doctor
5. **Compatibility/Regression**: test_compat_fixtures

---

## Coverage & Quality Gates

### Coverage Baseline (as of 2026-03-06)

**Configuration**: CI gate at 75% (from recent T-002 ticket)

```bash
# Reports missing lines per module
pytest --cov=helix --cov-report=term-missing
```

**Status**: Achieved 77% coverage in recent implementation (T-002 ticket)

### Performance Gate (scripts/bench_gate.py)

Runs threshold checks on:
- CDC chunking throughput
- Encode/decode performance
- Memory bounds

```bash
PYTHONPATH=src uv run python scripts/bench_gate.py
```

---

## Test Utilities & Helpers

### Custom Test Helpers

| Utility | File | Purpose |
|---------|------|---------|
| `_Resp` class | test_remote_pinning.py | Mocks urllib response objects |
| `_Proc` class | test_ml_hooks.py | Mocks subprocess.Popen return |
| `_tamper_integrity_field()` | test_container.py | Corrupts seed integrity sections for validation |
| `_write_seed()` | test_ml_hooks.py, test_container.py | Programmatic seed creation |
| `_write_fake_helix()` | test_dvc_bridge.py | Generates fake shell scripts for subprocess testing |
| `_load_manifest()` | test_compat_fixtures.py | Parses fixture index JSON |

### Import Patterns

**Core test imports**:
```python
from __future__ import annotations
import pytest
from pathlib import Path
from typer.testing import CliRunner
```

**Domain imports**:
```python
from helix.chunking import ChunkerConfig, chunk_bytes
from helix.codec import encode_file, decode_file, verify_seed
from helix.container import Recipe, RecipeOp, serialize_seed, parse_seed
from helix.errors import SeedFormatError, ExternalToolError
```

---

## Testing Constraints & Best Practices

### From CLAUDE.md (Testing Rules)

1. ✅ **IPFS tests skip gracefully** when CLI unavailable (test_ipfs_optional.py pattern)
2. ✅ **No large committed fixtures** — only 3 compatibility fixtures in version-gated `tests/fixtures/compat/v1/`
3. ✅ **Minimal test data** — programmatic seed creation via serialize_seed()
4. ✅ **Regeneration script** — `scripts/gen_compat_fixtures.py` updates fixtures on format changes
5. ⚠️ **Security-sensitive changes** — require risk notes (encryption, signatures, verify module)

### Linting & Pre-Commit

```bash
# Lint
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .

# Ruff config (pyproject.toml)
[tool.ruff]
line-length = 79
target-version = "py312"
select = ["E", "F", "I", "B", "UP"]
ignore = ["B008", "B904"]
```

---

## Test Execution & Debugging

### Quick Reference Commands

```bash
# Install dev deps
uv sync --no-editable --extra dev

# Full test suite with coverage
PYTHONPATH=src uv run --no-editable python -m pytest

# Single test file
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_chunking.py

# Single test function
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_chunking.py::test_cdc_buzhash_deterministic_boundaries

# With verbose output
PYTHONPATH=src uv run --no-editable python -m pytest -v

# Show print statements
PYTHONPATH=src uv run --no-editable python -m pytest -s

# Test only IPFS-related (skip others)
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_ipfs_*.py

# Test without coverage overhead
PYTHONPATH=src uv run --no-editable python -m pytest --no-cov
```

### Common Test Scenarios

**Isolated test development**:
```bash
# Develop a test in test_new_feature.py
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_new_feature.py::test_new_case -s
```

**Debug fixture failures**:
```bash
# Regenerate compat fixtures if format changes
PYTHONPATH=src uv run python scripts/gen_compat_fixtures.py
```

**Check IPFS availability**:
```bash
# Tests will auto-skip if `ipfs` CLI missing; force run with:
# (requires: ipfs daemon running, IPFS_PATH set)
PYTHONPATH=src uv run --no-editable python -m pytest tests/test_ipfs_optional.py -v
```

---

## Coverage Targets & Gaps

### Known Coverage Areas (77% baseline)

**Well-covered**:
- Core CDC chunking (determinism, buzhash, rabin)
- Container serialization/parsing
- Encryption/decryption flows
- Signature validation
- CLI integration (keygen, doctor, publish, pin)

**Partial coverage** (gaps from recent T-002 investigation):
- IPFS reliability edge cases (transient failures)
- OCI/ORAS bridge error paths
- MLflow/HF upload retry logic
- DVC script subprocess error handling

### Path to 80% (T-020 ticket objective)

Identified expansion areas:
1. IPFS retry exhaustion paths
2. Manifest integrity edge cases
3. Genome snapshot boundary conditions
4. OCI payload validation error cases
5. Remote pinning service fault injection

---

## Integration with CI/CD

### Pre-commit Enforcement

```bash
# Both must pass before commit
ruff check .
PYTHONPATH=src uv run --no-editable python -m pytest

# Performance gate (CI only)
PYTHONPATH=src uv run python scripts/bench_gate.py
```

### Coverage Gate (CI)

- **Threshold**: 75% (set in pyproject.toml)
- **Actual**: 77% (as of T-002 completion)
- **Report**: `--cov-report=term-missing` shows uncovered lines

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total test files** | 23 |
| **Total test functions** | 61+ |
| **Total lines of test code** | 1,768 |
| **Compat fixtures** | 3 (committed, versioned) |
| **Shared conftest.py** | None (inline fixtures) |
| **CLI test framework** | Typer CliRunner |
| **Mocking library** | pytest monkeypatch |
| **Coverage reporting** | pytest-cov (term-missing) |
| **CI coverage threshold** | 75% |
| **Actual coverage (T-002)** | 77% |

---

## Recommendations for Test Development

1. **New feature tests**: Create `tests/test_<feature>.py` with inline fixtures (no conftest needed)
2. **CLI commands**: Use `CliRunner` from `typer.testing`
3. **External tools**: Mock via `monkeypatch` (test_ml_hooks.py pattern)
4. **File I/O**: Use `tmp_path` fixture
5. **Optional IPFS**: Wrap in `if shutil.which("ipfs") is None: pytest.skip(...)`
6. **Error paths**: Use `pytest.raises()` with error code validation
7. **Fixtures**: Build programmatically via `serialize_seed()`, don't commit large binaries
8. **Compatibility**: Run `scripts/gen_compat_fixtures.py` when format changes
9. **Coverage**: Target >= 75% (CI gate); use `--cov-report=term-missing` to identify gaps
10. **Performance**: Use `scripts/bench_gate.py` for throughput-sensitive code

