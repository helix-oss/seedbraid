# Coverage Gap Analysis: `src/helix/diagnostics.py`

**Module**: `src/helix/diagnostics.py` (184 lines)  
**Current Coverage**: 75% (23 lines uncovered)  
**Missing Lines**: 50, 67-77, 89-104, 112-113, 121, 131-132, 156, 175-178

## Module Overview

The diagnostics module provides health checks for the Helix environment, verifying:
- Python version compatibility (3.12+)
- IPFS CLI availability and functionality
- IPFS repository path validity
- Genome storage path accessibility
- Compression library availability (zlib, zstandard)

### Key Data Structures
- `DoctorCheck`: Immutable check result with status (ok/warn/fail), detail, and next_action
- `DoctorReport`: Collection of checks with aggregation properties (ok_count, warn_count, fail_count, ok boolean)

---

## Coverage Gap Analysis by Line Group

### **Group 1: Line 50 (in `_check_python_version()`)**

**Location**: Lines 44-55  
**Function**: `_check_python_version()`  
**Gap**: Line 50 (failure path)

```python
def _check_python_version() -> DoctorCheck:
    major = os.sys.version_info.major
    minor = os.sys.version_info.minor
    detail = f"python={major}.{minor}"
    if (major, minor) >= (3, 12):
        return DoctorCheck(check="python", status="ok", detail=detail)
    return DoctorCheck(  # <-- LINE 50 (UNCOVERED)
        check="python",
        status="fail",
        detail=f"{detail} (requires >=3.12)",
        next_action="Install Python 3.12+ and recreate the project virtual environment.",
    )
```

**What it covers**: Failure case when Python version is <3.12  
**Difficulty**: **EASY**  
**Mocking required**: `monkeypatch.setattr("os.sys.version_info", ...)` to simulate Python 3.11 or earlier

**Test Strategy**:
```python
def test_check_python_version_fails_on_python_311(monkeypatch):
    # Create a mock version_info object
    mock_version = type('obj', (object,), {'major': 3, 'minor': 11})()
    monkeypatch.setattr("os.sys.version_info", mock_version)
    
    check = _check_python_version()
    assert check.status == "fail"
    assert "requires >=3.12" in check.detail
    assert check.next_action is not None
```

---

### **Group 2: Lines 67-77 (in `_check_ipfs_cli()`)**

**Location**: Lines 58-77  
**Function**: `_check_ipfs_cli()`  
**Gap**: Lines 67-77 (version check path)

```python
def _check_ipfs_cli() -> DoctorCheck:
    ipfs = shutil.which("ipfs")
    if ipfs is None:  # COVERED (tested in test_run_doctor_flags_missing_ipfs)
        return DoctorCheck(...)
    proc = subprocess.run([ipfs, "--version"], check=False, capture_output=True, text=True)
    if proc.returncode != 0:  # <-- LINE 68 (LIKELY COVERED)
        msg = proc.stderr.strip() or proc.stdout.strip() or "version check failed"
        return DoctorCheck(...)
    version = proc.stdout.strip() or proc.stderr.strip() or "unknown"  # <-- LINE 76 (UNCOVERED)
    return DoctorCheck(check="ipfs_cli", status="ok", detail=version)  # <-- LINE 77 (UNCOVERED)
```

**What it covers**:
- Successful IPFS CLI version check (lines 76-77)
- Various error message fallback scenarios in error case (line 69)

**Difficulty**: **EASY**  
**Mocking required**: 
- `monkeypatch.setattr("helix.diagnostics.shutil.which", lambda _: "/usr/bin/ipfs")`
- `monkeypatch.setattr("helix.diagnostics.subprocess.run", ...)` to simulate successful version output

**Test Strategy**:
```python
def test_check_ipfs_cli_succeeds_with_valid_binary(monkeypatch):
    monkeypatch.setattr("helix.diagnostics.shutil.which", lambda _: "/usr/bin/ipfs")
    
    def fake_run(cmd, **kwargs):
        result = type('obj', (object,), {
            'returncode': 0,
            'stdout': 'go-ipfs version 0.20.0\n',
            'stderr': ''
        })()
        return result
    
    monkeypatch.setattr("helix.diagnostics.subprocess.run", fake_run)
    
    check = _check_ipfs_cli()
    assert check.status == "ok"
    assert "0.20.0" in check.detail

def test_check_ipfs_cli_fails_on_returncode(monkeypatch):
    monkeypatch.setattr("helix.diagnostics.shutil.which", lambda _: "/usr/bin/ipfs")
    
    def fake_run(cmd, **kwargs):
        result = type('obj', (object,), {
            'returncode': 1,
            'stdout': '',
            'stderr': 'permission denied'
        })()
        return result
    
    monkeypatch.setattr("helix.diagnostics.subprocess.run", fake_run)
    
    check = _check_ipfs_cli()
    assert check.status == "fail"
    assert "permission denied" in check.detail
```

---

### **Group 3: Lines 89-104 (in `_check_ipfs_path()`)**

**Location**: Lines 80-104  
**Function**: `_check_ipfs_path()`  
**Gap**: Lines 89-104 (IPFS_PATH environment variable set scenarios)

```python
def _check_ipfs_path() -> DoctorCheck:
    ipfs_path = os.environ.get("IPFS_PATH")
    if not ipfs_path:  # COVERED (test_run_doctor_flags_missing_ipfs)
        return DoctorCheck(...)
    p = Path(ipfs_path)
    if not p.exists():  # <-- LINE 90-95 (UNCOVERED: IPFS_PATH set but doesn't exist)
        return DoctorCheck(...)
    if not p.is_dir():  # <-- LINE 97-102 (UNCOVERED: IPFS_PATH is file, not dir)
        return DoctorCheck(...)
    return DoctorCheck(check="ipfs_repo", status="ok", detail=f"IPFS_PATH={p}")  # <-- LINE 104 (UNCOVERED: success case)
```

**What it covers**:
- IPFS_PATH is set and valid directory (success, line 104)
- IPFS_PATH is set but directory doesn't exist (warning, lines 90-95)
- IPFS_PATH is set but is a file instead of directory (fail, lines 97-102)

**Difficulty**: **EASY**  
**Mocking required**: Filesystem path mocking via tmp_path or monkeypatch.setenv

**Test Strategy**:
```python
def test_check_ipfs_path_warns_when_unset(monkeypatch):
    # This may already be partially covered
    monkeypatch.delenv("IPFS_PATH", raising=False)
    check = _check_ipfs_path()
    assert check.status == "warn"
    assert "IPFS_PATH is unset" in check.detail

def test_check_ipfs_path_warns_when_nonexistent(tmp_path, monkeypatch):
    bad_path = tmp_path / "nonexistent" / "ipfs"
    monkeypatch.setenv("IPFS_PATH", str(bad_path))
    
    check = _check_ipfs_path()
    assert check.status == "warn"
    assert "does not exist" in check.detail

def test_check_ipfs_path_fails_when_file_not_dir(tmp_path, monkeypatch):
    file_path = tmp_path / "ipfs_file"
    file_path.write_text("not a directory")
    monkeypatch.setenv("IPFS_PATH", str(file_path))
    
    check = _check_ipfs_path()
    assert check.status == "fail"
    assert "not a directory" in check.detail

def test_check_ipfs_path_succeeds_when_valid_dir(tmp_path, monkeypatch):
    valid_path = tmp_path / "ipfs_repo"
    valid_path.mkdir()
    monkeypatch.setenv("IPFS_PATH", str(valid_path))
    
    check = _check_ipfs_path()
    assert check.status == "ok"
    assert str(valid_path) in check.detail
```

---

### **Group 4: Lines 112-113 (in `_check_genome_path()`)**

**Location**: Lines 107-139  
**Function**: `_check_genome_path(genome_path: Path)`  
**Gap**: Lines 112-113 (OSError in mkdir)

```python
def _check_genome_path(genome_path: Path) -> DoctorCheck:
    db_path = resolve_genome_db_path(genome_path)
    parent = db_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # <-- LINES 112-113 (UNCOVERED: mkdir fails)
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"cannot create parent directory {parent}: {exc}",
            next_action="Choose a writable --genome path.",
        )
    # ... more checks follow
```

**What it covers**: OSError during directory creation (e.g., permission denied, readonly filesystem)

**Difficulty**: **MEDIUM**  
**Mocking required**: `monkeypatch.setattr("pathlib.Path.mkdir", side_effect=OSError(...))`

**Test Strategy**:
```python
def test_check_genome_path_fails_on_mkdir_error(tmp_path, monkeypatch):
    def failing_mkdir(self, parents=False, exist_ok=False):
        raise OSError("Permission denied")
    
    genome_path = tmp_path / "genome"
    monkeypatch.setattr("pathlib.Path.mkdir", failing_mkdir)
    
    check = _check_genome_path(genome_path)
    assert check.status == "fail"
    assert "cannot create parent directory" in check.detail
```

---

### **Group 5: Line 121 (in `_check_genome_path()`)**

**Location**: Lines 120-126  
**Function**: `_check_genome_path(genome_path: Path)`  
**Gap**: Line 121 (directory not writable)

```python
def _check_genome_path(genome_path: Path) -> DoctorCheck:
    # ... previous checks ...
    if not os.access(parent, os.W_OK):  # <-- LINE 121 (UNCOVERED: not writable)
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"directory is not writable: {parent}",
            next_action="Adjust directory permissions or select another --genome path.",
        )
```

**What it covers**: Directory exists but is not writable (permission check)

**Difficulty**: **MEDIUM**  
**Mocking required**: `monkeypatch.setattr("os.access", lambda path, mode: False)`

**Test Strategy**:
```python
def test_check_genome_path_fails_when_not_writable(tmp_path, monkeypatch):
    genome_path = tmp_path / "genome"
    genome_path.mkdir()
    
    # Mock os.access to simulate unwritable directory
    monkeypatch.setattr("os.access", lambda path, mode: False)
    
    check = _check_genome_path(genome_path)
    assert check.status == "fail"
    assert "not writable" in check.detail
```

---

### **Group 6: Lines 131-132 (in `_check_genome_path()`)**

**Location**: Lines 128-137  
**Function**: `_check_genome_path(genome_path: Path)`  
**Gap**: Lines 131-132 (OSError during write test)

```python
def _check_genome_path(genome_path: Path) -> DoctorCheck:
    # ... previous checks ...
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".helix-doctor-", delete=True):
            pass
    except OSError as exc:  # <-- LINES 131-132 (UNCOVERED: write test fails)
        return DoctorCheck(
            check="genome_path",
            status="fail",
            detail=f"write test failed under {parent}: {exc}",
            next_action="Fix filesystem permissions for genome storage.",
        )
```

**What it covers**: Actual write operation fails (e.g., disk full, filesystem readonly)

**Difficulty**: **MEDIUM**  
**Mocking required**: `monkeypatch.setattr("tempfile.NamedTemporaryFile", side_effect=OSError(...))`

**Test Strategy**:
```python
def test_check_genome_path_fails_on_write_test(tmp_path, monkeypatch):
    genome_path = tmp_path / "genome"
    genome_path.mkdir()
    
    def failing_tempfile(*args, **kwargs):
        raise OSError("No space left on device")
    
    monkeypatch.setattr("tempfile.NamedTemporaryFile", failing_tempfile)
    
    check = _check_genome_path(genome_path)
    assert check.status == "fail"
    assert "write test failed" in check.detail
```

---

### **Group 7: Line 156 (in `_check_compression()`)**

**Location**: Lines 142-163  
**Function**: `_check_compression() -> list[DoctorCheck]`  
**Gap**: Line 156 (zstandard IS available)

```python
def _check_compression() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = [
        DoctorCheck(check="compression_zlib", status="ok", detail="zlib available (stdlib)")
    ]
    if importlib.util.find_spec("zstandard") is None:  # COVERED (test_doctor_cli_exit_zero_with_only_warn mocks this)
        checks.append(
            DoctorCheck(
                check="compression_zstd",
                status="warn",
                detail="optional dependency 'zstandard' is not installed",
                next_action="Run `uv sync --extra zstd` to enable --compression zstd.",
            )
        )
    else:  # <-- LINE 156 (UNCOVERED: zstandard IS installed)
        checks.append(
            DoctorCheck(
                check="compression_zstd",
                status="ok",
                detail="zstandard available",
            )
        )
    return checks
```

**What it covers**: Success case when zstandard library is available

**Difficulty**: **EASY**  
**Mocking required**: `monkeypatch.setattr("importlib.util.find_spec", lambda name: Mock())` (return non-None)

**Test Strategy**:
```python
def test_check_compression_detects_zstandard_available(monkeypatch):
    # Mock find_spec to return a module spec (non-None = installed)
    mock_spec = type('obj', (object,), {})()
    monkeypatch.setattr("importlib.util.find_spec", lambda name: mock_spec)
    
    checks = _check_compression()
    zstd_check = next(c for c in checks if c.check == "compression_zstd")
    assert zstd_check.status == "ok"
    assert "available" in zstd_check.detail
```

---

### **Group 8: Lines 175-178 (in `run_doctor()`)**

**Location**: Lines 166-183  
**Function**: `run_doctor(genome_path: str | Path) -> DoctorReport`  
**Gap**: Lines 175-178 (exception handling)

```python
def run_doctor(genome_path: str | Path) -> DoctorReport:
    path = Path(genome_path)
    checks: list[DoctorCheck] = []
    try:
        checks.append(_check_python_version())
        checks.append(_check_ipfs_cli())
        checks.append(_check_ipfs_path())
        checks.append(_check_genome_path(path))
        checks.extend(_check_compression())
    except HelixError:  # <-- LINE 175 (UNCOVERED: catch and re-raise HelixError)
        raise
    except Exception as exc:  # noqa: BLE001  <-- LINES 177-182 (UNCOVERED: wrap unexpected exceptions)
        raise ExternalToolError(
            f"doctor failed unexpectedly: {exc}",
            code="HELIX_E_DOCTOR_CHECK",
            next_action="Re-run `helix doctor --genome <path>` and inspect environment setup.",
        ) from exc
    return DoctorReport(checks=checks)
```

**What it covers**:
- HelixError is caught and re-raised without wrapping (line 175-176)
- Unexpected exceptions are wrapped in ExternalToolError (lines 177-182)

**Difficulty**: **MEDIUM**  
**Mocking required**: Simulate exceptions in check functions via monkeypatch

**Test Strategy**:
```python
def test_run_doctor_reraises_helix_error(tmp_path, monkeypatch):
    def failing_check(*args, **kwargs):
        raise HelixError("Test error", code="TEST_CODE")
    
    monkeypatch.setattr("helix.diagnostics._check_python_version", failing_check)
    
    with pytest.raises(HelixError, match="Test error"):
        run_doctor(tmp_path)

def test_run_doctor_wraps_unexpected_exception(tmp_path, monkeypatch):
    def failing_check(*args, **kwargs):
        raise ValueError("Unexpected issue")
    
    monkeypatch.setattr("helix.diagnostics._check_ipfs_cli", failing_check)
    
    with pytest.raises(ExternalToolError, match="doctor failed unexpectedly"):
        run_doctor(tmp_path)
```

---

## Summary Table

| Line(s) | Function | Gap Type | Difficulty | Mocking Needed | Est. Time |
|---------|----------|----------|------------|---|----------|
| 50 | `_check_python_version()` | Python <3.12 failure | EASY | version_info mock | 5 min |
| 67-77 | `_check_ipfs_cli()` | Successful version check | EASY | subprocess mock | 10 min |
| 89-104 | `_check_ipfs_path()` | IPFS_PATH scenarios (3 cases) | EASY | tmp_path/setenv | 15 min |
| 112-113 | `_check_genome_path()` | mkdir OSError | MEDIUM | Path.mkdir mock | 10 min |
| 121 | `_check_genome_path()` | not writable | MEDIUM | os.access mock | 10 min |
| 131-132 | `_check_genome_path()` | write test OSError | MEDIUM | tempfile mock | 10 min |
| 156 | `_check_compression()` | zstandard available | EASY | find_spec mock | 5 min |
| 175-178 | `run_doctor()` | Exception handling (2 cases) | MEDIUM | exception injection | 10 min |

**Total Estimated Implementation Time**: ~75 minutes  
**Expected Coverage After**: 100% (all 23 lines covered)

---

## Implementation Roadmap

### Phase 1: Easy Tests (Groups 1, 2, 7) — 20 minutes
- Test python version < 3.12 failure
- Test ipfs CLI successful version check
- Test zstandard library detection

### Phase 2: Path Tests (Group 3) — 15 minutes
- Three test cases for IPFS_PATH scenarios
- Use tmp_path and setenv for isolation

### Phase 3: Genome Path Tests (Groups 4, 5, 6) — 30 minutes
- Three test cases for mkdir failure, writable check, write test
- Mock filesystem operations carefully

### Phase 4: Exception Handling (Group 8) — 10 minutes
- Two test cases for HelixError and unexpected exceptions
- Use monkeypatch to inject exceptions into check functions

---

## Notes

1. **Test File**: All tests should be added to `/Users/kytk/workspace/repos/helix/tests/test_doctor.py`

2. **Existing Test Patterns**: The test file already uses:
   - `monkeypatch` fixture for environment manipulation
   - `tmp_path` fixture for temporary directories
   - `CliRunner` for CLI integration tests
   - Follow these patterns for consistency

3. **Coverage Verification**:
   ```bash
   PYTHONPATH=src uv run --no-editable python -m pytest tests/test_doctor.py --cov=src/helix/diagnostics --cov-report=term-missing
   ```

4. **Risk Considerations**:
   - Filesystem mocking (mkdir, access, tempfile) requires careful isolation
   - Subprocess mocking for ipfs version check should use realistic output
   - Exception injection tests should verify both the exception type and wrapped message

5. **Future Improvements**:
   - Consider parameterized tests for multiple scenarios (e.g., different Python versions)
   - Add integration tests that run against real filesystem and IPFS when available
   - Document expected behavior for different platform/environment combinations
