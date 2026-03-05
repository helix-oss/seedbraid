# Test Coverage Gap Analysis: `src/helix/perf.py`

**Date**: 2026-03-06  
**File**: `src/helix/perf.py` (174 lines)  
**Coverage Status**: Missing lines: 28, 47, 51-60, 72-96, 117-141  
**Existing Tests**: `tests/test_perf_gates.py` (only 2 tests for `evaluate_benchmark_gates`)

---

## Coverage Overview

### Current Test Coverage

The project currently has **minimal test coverage** for `perf.py`:
- `test_perf_gates.py`: 2 tests targeting only `evaluate_benchmark_gates()` function
- No tests for: dataclass properties, `_run_case()`, `run_shifted_dedup_benchmark()`, or JSON serialization
- Coverage estimate: ~15-20% (only the gate evaluation function)

### Missing Lines Grouped by Function

---

## Gap 1: `BenchCaseResult.reuse_ratio` property (Line 28)

**Location**: Lines 25-29  
**Function**: `BenchCaseResult.reuse_ratio` property

```python
@property
def reuse_ratio(self) -> float:
    if self.total_chunks == 0:
        return 0.0
    return self.reused_chunks / self.total_chunks  # LINE 28
```

### What it covers
- Edge case: `total_chunks == 0` should return 0.0 (safeguard against division by zero)
- Normal case: ratio calculation for chunk reuse

### Difficulty: **Easy**

### Test Strategy
```python
# Edge case test
def test_bench_case_result_reuse_ratio_zero_chunks():
    result = BenchCaseResult(
        chunker="test",
        total_chunks=0,
        reused_chunks=0,
        new_chunks=0,
        seed_size_bytes=100,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    assert result.reuse_ratio == 0.0

# Normal case test
def test_bench_case_result_reuse_ratio_normal():
    result = BenchCaseResult(
        chunker="test",
        total_chunks=100,
        reused_chunks=75,
        new_chunks=25,
        seed_size_bytes=100,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    assert result.reuse_ratio == 0.75
```

### Mocking needed: None

---

## Gap 2: `ShiftedDedupBenchmark.seed_size_ratio` property (Line 47)

**Location**: Lines 44-48  
**Function**: `ShiftedDedupBenchmark.seed_size_ratio` property

```python
@property
def seed_size_ratio(self) -> float:
    if self.fixed.seed_size_bytes <= 0:
        return 1.0
    return self.cdc.seed_size_bytes / self.fixed.seed_size_bytes  # LINE 47
```

### What it covers
- Edge case: `fixed.seed_size_bytes <= 0` should return 1.0 (safeguard; prevents division by zero and represents no improvement)
- Normal case: ratio of CDC seed size to fixed seed size

### Difficulty: **Easy**

### Test Strategy
```python
# Edge case: zero or negative fixed seed size
def test_shifted_dedup_benchmark_seed_size_ratio_zero_fixed():
    fixed = BenchCaseResult(
        chunker="fixed",
        total_chunks=100,
        reused_chunks=50,
        new_chunks=50,
        seed_size_bytes=0,  # Edge case
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    cdc = BenchCaseResult(
        chunker="cdc_buzhash",
        total_chunks=100,
        reused_chunks=75,
        new_chunks=25,
        seed_size_bytes=800,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    report = ShiftedDedupBenchmark(
        source_size_bytes=1_000_000,
        insert_offset=100_000,
        inserted_size_bytes=1,
        fixed=fixed,
        cdc=cdc,
    )
    assert report.seed_size_ratio == 1.0

# Normal case
def test_shifted_dedup_benchmark_seed_size_ratio_normal():
    # ... (use existing _report helper from test_perf_gates.py)
    report = _report(
        reuse_improvement_bps=100,
        seed_size_ratio=0.8,
        throughput=10.0,
    )
    assert report.seed_size_ratio == 0.8
```

### Mocking needed: None

---

## Gap 3: `ShiftedDedupBenchmark.to_json()` method (Lines 51-60)

**Location**: Lines 50-60  
**Function**: `ShiftedDedupBenchmark.to_json()` method

```python
def to_json(self) -> str:
    payload = {
        "source_size_bytes": self.source_size_bytes,
        "insert_offset": self.insert_offset,
        "inserted_size_bytes": self.inserted_size_bytes,
        "reuse_improvement_bps": self.reuse_improvement_bps,
        "seed_size_ratio": self.seed_size_ratio,
        "fixed": asdict(self.fixed),
        "cdc": asdict(self.cdc),
    }
    return json.dumps(payload, indent=2, sort_keys=True)
```

### What it covers
- JSON serialization of benchmark report
- Includes all properties: `reuse_improvement_bps`, `seed_size_ratio`
- Uses `asdict()` for nested dataclass conversion
- Proper JSON formatting (indentation, sorting)
- All 8 payload fields

### Difficulty: **Easy**

### Test Strategy
```python
import json

def test_shifted_dedup_benchmark_to_json():
    fixed = BenchCaseResult(
        chunker="fixed",
        total_chunks=100,
        reused_chunks=50,
        new_chunks=50,
        seed_size_bytes=1000,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    cdc = BenchCaseResult(
        chunker="cdc_buzhash",
        total_chunks=100,
        reused_chunks=75,
        new_chunks=25,
        seed_size_bytes=800,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )
    report = ShiftedDedupBenchmark(
        source_size_bytes=1_000_000,
        insert_offset=100_000,
        inserted_size_bytes=1,
        fixed=fixed,
        cdc=cdc,
    )
    
    json_str = report.to_json()
    
    # Verify it's valid JSON
    data = json.loads(json_str)
    
    # Verify top-level keys exist
    assert "source_size_bytes" in data
    assert "insert_offset" in data
    assert "inserted_size_bytes" in data
    assert "reuse_improvement_bps" in data
    assert "seed_size_ratio" in data
    assert "fixed" in data
    assert "cdc" in data
    
    # Verify values
    assert data["source_size_bytes"] == 1_000_000
    assert data["insert_offset"] == 100_000
    assert data["inserted_size_bytes"] == 1
    assert data["fixed"]["chunker"] == "fixed"
    assert data["cdc"]["chunker"] == "cdc_buzhash"
    
    # Verify JSON formatting (sort_keys=True, indent=2)
    assert "\n" in json_str  # Has newlines due to indent=2
    
    # Verify keys are sorted
    lines = json_str.split("\n")
    # Check that keys appear in alphabetical order within their section
```

### Mocking needed: None

---

## Gap 4: `_run_case()` function (Lines 72-96)

**Location**: Lines 63-105  
**Function**: `_run_case()` private helper

```python
def _run_case(
    chunker: str,
    cfg: ChunkerConfig,
    base: Path,
    shifted: Path,
    workspace: Path,
    *,
    compression: str,
) -> BenchCaseResult:
    genome = workspace / f"genome-{chunker}"
    seed = workspace / f"shifted-{chunker}.hlx"

    start_prime = time.perf_counter()
    prime_genome(base, genome, chunker=chunker, cfg=cfg)
    prime_seconds = time.perf_counter() - start_prime

    start_encode = time.perf_counter()
    encode_stats = encode_file(
        in_path=shifted,
        genome_path=genome,
        out_seed_path=seed,
        chunker=chunker,
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression=compression,
    )
    encode_seconds = time.perf_counter() - start_encode
    throughput = 0.0
    source_size = shifted.stat().st_size
    if encode_seconds > 0:
        throughput = source_size / encode_seconds / (1024 * 1024)  # LINES 91-94

    return BenchCaseResult(...)
```

### What it covers
- File I/O: genome and seed file path construction
- Timing: `time.perf_counter()` for `prime_genome()` and `encode_file()`
- Integration with `prime_genome()` from codec module
- Integration with `encode_file()` from codec module
- EncodeStats handling and chunk statistics
- Throughput calculation: handles `encode_seconds > 0` edge case (line 93)
- File size retrieval via `Path.stat()`

### Difficulty: **Medium**

### Test Strategy

This is a private function that orchestrates codec operations. Testing it directly requires:
1. Mock `prime_genome()` and `encode_file()` from `codec` module
2. Create temporary files or mock `Path` operations
3. Verify timing measurements and throughput calculations

```python
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path
import tempfile

def test_run_case_timing_and_throughput():
    """Test _run_case() throughput calculation."""
    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td)
        base = workspace / "base.bin"
        shifted = workspace / "shifted.bin"
        
        # Create small test files (1 MiB)
        test_data = b"x" * (1024 * 1024)
        base.write_bytes(test_data)
        shifted.write_bytes(test_data)
        
        with patch("helix.perf.prime_genome") as mock_prime, \
             patch("helix.perf.encode_file") as mock_encode:
            
            # Mock encode_stats return value
            mock_stats = MagicMock()
            mock_stats.total_chunks = 100
            mock_stats.reused_chunks = 50
            mock_stats.new_chunks = 50
            mock_encode.return_value = mock_stats
            
            from helix.perf import _run_case
            from helix.chunking import ChunkerConfig
            
            cfg = ChunkerConfig(
                min_size=4_096,
                avg_size=16_384,
                max_size=65_536,
                window_size=32,
            )
            
            result = _run_case(
                chunker="cdc_buzhash",
                cfg=cfg,
                base=base,
                shifted=shifted,
                workspace=workspace,
                compression="zlib",
            )
            
            # Verify function calls
            mock_prime.assert_called_once()
            mock_encode.assert_called_once()
            
            # Verify result structure
            assert result.chunker == "cdc_buzhash"
            assert result.total_chunks == 100
            assert result.reused_chunks == 50
            assert result.new_chunks == 50
            
            # Verify timing is non-negative
            assert result.prime_seconds >= 0
            assert result.encode_seconds >= 0
            
            # Verify throughput is > 0 (1 MiB file encoded in finite time)
            assert result.encode_throughput_mib_s > 0

def test_run_case_zero_encode_seconds():
    """Test _run_case() throughput calculation when encode_seconds is 0."""
    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td)
        base = workspace / "base.bin"
        shifted = workspace / "shifted.bin"
        
        # Create files
        base.write_bytes(b"test")
        shifted.write_bytes(b"test")
        
        with patch("helix.perf.prime_genome"), \
             patch("helix.perf.encode_file") as mock_encode, \
             patch("helix.perf.time.perf_counter") as mock_time:
            
            # Simulate zero elapsed time
            mock_time.side_effect = [0.0, 0.0, 0.0, 0.0]
            
            mock_stats = MagicMock()
            mock_stats.total_chunks = 1
            mock_stats.reused_chunks = 0
            mock_stats.new_chunks = 1
            mock_encode.return_value = mock_stats
            
            from helix.perf import _run_case
            from helix.chunking import ChunkerConfig
            
            cfg = ChunkerConfig()
            result = _run_case(
                chunker="fixed",
                cfg=cfg,
                base=base,
                shifted=shifted,
                workspace=workspace,
                compression="zlib",
            )
            
            # When encode_seconds == 0, throughput should be 0.0 (line 91)
            assert result.encode_throughput_mib_s == 0.0
```

### Mocking needed:
- `helix.codec.prime_genome()` - to avoid actual genome building
- `helix.codec.encode_file()` - to avoid actual encoding; mock return `EncodeStats`
- `time.perf_counter()` - optional, for testing edge cases (zero elapsed time)
- `Path` operations - can use real temp files or mock

---

## Gap 5: `run_shifted_dedup_benchmark()` function (Lines 117-141)

**Location**: Lines 108-147  
**Function**: `run_shifted_dedup_benchmark()` main public benchmarking function

```python
def run_shifted_dedup_benchmark(
    *,
    total_size_bytes: int = 3_200_000,
    insert_offset: int = 100_000,
    inserted: bytes = b"Z",
    random_seed: int = 42,
    chunker_cfg: ChunkerConfig | None = None,
    compression: str = "zlib",
) -> ShiftedDedupBenchmark:
    cfg = chunker_cfg or ChunkerConfig(...)  # LINES 117-122
    if total_size_bytes <= 0:
        raise ValueError("total_size_bytes must be > 0")
    if not (0 <= insert_offset <= total_size_bytes):
        raise ValueError("insert_offset must be in [0, total_size_bytes]")

    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td)
        base = workspace / "base.bin"
        shifted = workspace / "shifted.bin"

        rng = random.Random(random_seed)
        original = bytes(rng.randrange(0, 256) for _ in range(total_size_bytes))
        base.write_bytes(original)
        shifted.write_bytes(original[:insert_offset] + inserted + original[insert_offset:])

        fixed = _run_case("fixed", cfg, base, shifted, workspace, compression=compression)
        cdc = _run_case("cdc_buzhash", cfg, base, shifted, workspace, compression=compression)

        return ShiftedDedupBenchmark(...)  # LINES 141-147
```

### What it covers
- **Validation (lines 123-126)**: 
  - `total_size_bytes > 0` constraint
  - `insert_offset` within bounds `[0, total_size_bytes]`
- **Config defaults (lines 117-122)**: Use provided or default `ChunkerConfig`
- **File generation (lines 128-136)**:
  - Deterministic random data via seeded RNG
  - Byte insertion at specified offset
  - File I/O via `Path.write_bytes()`
- **Benchmark execution (lines 138-139)**:
  - Calls `_run_case()` for both "fixed" and "cdc_buzhash" chunkers
- **Result construction (lines 141-147)**: Assembles and returns `ShiftedDedupBenchmark`

### Difficulty: **Medium**

### Test Strategy

This is the main public function and should have comprehensive test coverage:

```python
import pytest
from helix.perf import run_shifted_dedup_benchmark, ShiftedDedupBenchmark
from helix.chunking import ChunkerConfig

# Test 1: Invalid total_size_bytes
def test_run_shifted_dedup_benchmark_invalid_total_size():
    """Test validation: total_size_bytes must be > 0."""
    with pytest.raises(ValueError, match="total_size_bytes must be > 0"):
        run_shifted_dedup_benchmark(total_size_bytes=0)
    
    with pytest.raises(ValueError, match="total_size_bytes must be > 0"):
        run_shifted_dedup_benchmark(total_size_bytes=-1)

# Test 2: Invalid insert_offset
def test_run_shifted_dedup_benchmark_invalid_insert_offset():
    """Test validation: insert_offset must be in [0, total_size_bytes]."""
    # Offset > total_size_bytes
    with pytest.raises(ValueError, match="insert_offset must be in"):
        run_shifted_dedup_benchmark(
            total_size_bytes=1000,
            insert_offset=1001,
        )
    
    # Offset < 0
    with pytest.raises(ValueError, match="insert_offset must be in"):
        run_shifted_dedup_benchmark(
            total_size_bytes=1000,
            insert_offset=-1,
        )

# Test 3: Valid config defaults
def test_run_shifted_dedup_benchmark_default_config():
    """Test that default ChunkerConfig is used when not provided."""
    # Use small size for fast test
    report = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
    )
    
    assert isinstance(report, ShiftedDedupBenchmark)
    assert report.source_size_bytes == 100_000
    assert report.insert_offset == 50_000
    assert report.inserted_size_bytes == 1  # Default b"Z"
    assert report.fixed.chunker == "fixed"
    assert report.cdc.chunker == "cdc_buzhash"

# Test 4: Custom config
def test_run_shifted_dedup_benchmark_custom_config():
    """Test with custom ChunkerConfig."""
    cfg = ChunkerConfig(
        min_size=2_048,
        avg_size=8_192,
        max_size=32_768,
        window_size=16,
    )
    report = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
        chunker_cfg=cfg,
    )
    
    assert isinstance(report, ShiftedDedupBenchmark)
    # Config is passed through; verify by checking results are valid
    assert report.fixed.total_chunks > 0
    assert report.cdc.total_chunks > 0

# Test 5: Deterministic results with same seed
def test_run_shifted_dedup_benchmark_deterministic():
    """Test that same random_seed produces same file data."""
    report1 = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
        random_seed=42,
    )
    
    report2 = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
        random_seed=42,
    )
    
    # Same seed should produce same chunk counts
    assert report1.fixed.total_chunks == report2.fixed.total_chunks
    assert report1.cdc.total_chunks == report2.cdc.total_chunks

# Test 6: Edge case - insert_offset at boundaries
def test_run_shifted_dedup_benchmark_insert_offset_boundaries():
    """Test insert_offset at 0 and total_size_bytes."""
    # Offset at 0 (prepend)
    report1 = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=0,
    )
    assert report1.insert_offset == 0
    
    # Offset at total_size_bytes (append)
    report2 = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=100_000,
    )
    assert report2.insert_offset == 100_000

# Test 7: Custom inserted bytes
def test_run_shifted_dedup_benchmark_custom_inserted():
    """Test with custom inserted bytes."""
    report = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
        inserted=b"HELLO_WORLD",
    )
    
    assert report.inserted_size_bytes == len(b"HELLO_WORLD")
    assert report.inserted_size_bytes == 11

# Test 8: Result structure and properties
def test_run_shifted_dedup_benchmark_result_structure():
    """Test returned ShiftedDedupBenchmark has valid structure."""
    report = run_shifted_dedup_benchmark(
        total_size_bytes=100_000,
        insert_offset=50_000,
    )
    
    # Check all properties exist
    assert hasattr(report, "source_size_bytes")
    assert hasattr(report, "insert_offset")
    assert hasattr(report, "inserted_size_bytes")
    assert hasattr(report, "fixed")
    assert hasattr(report, "cdc")
    
    # Check properties are accessible
    _ = report.reuse_improvement_bps
    _ = report.seed_size_ratio
    
    # Check fixed and cdc are BenchCaseResult
    assert report.fixed.chunker == "fixed"
    assert report.cdc.chunker == "cdc_buzhash"
```

### Mocking needed:
- **Optional**: Mock `prime_genome()` and `encode_file()` for unit test speed (avoid actual codec work)
- **Better**: Run integration tests without mocking (test via `_run_case` integration)
- **Real files**: Use tempfile or fixture-based approach for actual file I/O

---

## Summary Table

| Gap | Lines | Function | Coverage | Difficulty | Tests Needed |
|-----|-------|----------|----------|------------|--------------|
| 1 | 28 | `BenchCaseResult.reuse_ratio` | Property edge case (zero chunks) | Easy | 2 |
| 2 | 47 | `ShiftedDedupBenchmark.seed_size_ratio` | Property edge case (zero fixed) | Easy | 2 |
| 3 | 51-60 | `ShiftedDedupBenchmark.to_json()` | JSON serialization | Easy | 1 |
| 4 | 72-96 | `_run_case()` | File I/O, timing, throughput calc | Medium | 2 |
| 5 | 117-141 | `run_shifted_dedup_benchmark()` | Validation, config, main loop | Medium | 8 |

---

## Recommended Test Implementation Plan

### Phase 1: Easy Wins (Easy difficulty) - 5 tests
1. `test_bench_case_result_reuse_ratio_zero_chunks()`
2. `test_bench_case_result_reuse_ratio_normal()`
3. `test_shifted_dedup_benchmark_seed_size_ratio_zero_fixed()`
4. `test_shifted_dedup_benchmark_seed_size_ratio_normal()`
5. `test_shifted_dedup_benchmark_to_json()`

**Expected coverage improvement**: ~30 lines (100% of gaps 1, 2, 3)

### Phase 2: Medium Complexity (Medium difficulty) - 10 tests
1. `test_run_case_timing_and_throughput()` with real temp files
2. `test_run_case_zero_encode_seconds()` with mocked timing
3. `test_run_shifted_dedup_benchmark_invalid_total_size()`
4. `test_run_shifted_dedup_benchmark_invalid_insert_offset()`
5. `test_run_shifted_dedup_benchmark_default_config()`
6. `test_run_shifted_dedup_benchmark_custom_config()`
7. `test_run_shifted_dedup_benchmark_deterministic()`
8. `test_run_shifted_dedup_benchmark_insert_offset_boundaries()`
9. `test_run_shifted_dedup_benchmark_custom_inserted()`
10. `test_run_shifted_dedup_benchmark_result_structure()`

**Expected coverage improvement**: ~50 lines (100% of gaps 4, 5)

### Implementation Notes
- **Location**: Create `tests/test_perf.py` (new file; test_perf_gates.py tests only gates)
- **Fixtures**: Reuse `_report()` helper from test_perf_gates.py or move to conftest
- **Speed**: 
  - Easy tests: <100ms total
  - Medium tests with real codec: 5-15s total (depends on file size)
  - Can use `pytest.mark.slow` for integration tests
- **Coverage target**: 100% coverage of perf.py after implementation

---

## Key Testing Insights

### 1. Dataclass Properties with Edge Cases
Both `reuse_ratio` and `seed_size_ratio` have division-by-zero guards. These guards are critical for robustness:
- Empty benchmarks (0 chunks) should not crash
- Invalid states (0 or negative seed size) should not crash
- Test both paths: guard returns fallback value AND normal calculation

### 2. Private Function Testing Strategy
`_run_case()` is private but essential. Options:
- **Test via integration**: Call `run_shifted_dedup_benchmark()` which calls `_run_case()`
- **Test via mocking**: Mock codec functions to isolate `_run_case()` logic
- **Hybrid**: Unit tests with mocks + integration tests for real codec

### 3. Temporary Files and Cleanup
- Use `tempfile.TemporaryDirectory()` context manager (cleanup automatic)
- Use `Path.write_bytes()` for deterministic file creation
- Avoid fixtures for large binary data (keep tests fast)

### 4. JSON Serialization Testing
- Verify valid JSON output: `json.loads()` should not raise
- Check all expected keys present (8 fields)
- Verify nested structures: `fixed` and `cdc` as dicts
- Verify formatting: proper indentation and key sorting

### 5. Determinism and Randomness
- Test randomness via seeded `random.Random(seed)`
- Same seed should produce identical file data
- Different seeds should produce different data (optional edge case)
- Verify dedup results are reproducible

---

## Risk Assessment

### Low Risk
- Property tests (edge cases, simple math)
- JSON serialization (no side effects)
- Validation tests (input validation)

### Medium Risk
- `_run_case()` mocking (must carefully mock codec return values)
- Timing measurements (inherent variability; use loose assertions or skip timing checks)
- Integration tests (depend on codec working correctly)

### Mitigation
- Use `pytest.mark.slow` for long-running integration tests
- Mock codec functions by default; run integration tests separately if needed
- Use tight tolerances only for deterministic values (chunk counts); avoid timing assertions

