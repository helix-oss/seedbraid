# PEP8 Cleanup: scripts/ and tests/ (line-length=79)

**Date**: 2026-03-07
**Category**: CodeQuality
**Size**: M
**Root cause**: Commits `86898fa` (src/ cleanup) and `674da6f` (config change) left scripts/ and tests/ non-compliant with `line-length = 79`

---

## Overview and Goals

1. Resolve all 133 ruff lint errors (130 E501 + 3 I001) in `scripts/` and `tests/`
2. Restore CI green status
3. Zero behavioral changes to any test or script
4. Single conventional-commit or at most 2 commits (auto-fix + manual)

---

## Affected Files and Components

### scripts/ (3 files, 35 errors: 32 E501 + 3 I001)

| File | E501 | I001 | Longest | Dominant Pattern |
|------|------|------|---------|-----------------|
| `scripts/ml_hooks.py` | 14 | 1 | 98 | argparse help strings, monkeypatch lines |
| `scripts/oras_seed.py` | 6 | 0 | ~85 | argparse help strings, f-string output |
| `scripts/gen_compat_fixtures.py` | 3 | 1 | 97 | Recipe constructor, json.dumps call |
| `scripts/bench_gate.py` | 1 | 1 | 80 | description string |
| `scripts/bench_shifted_dedup.py` | 8 | 0 | ~90 | f-string print statements |

### tests/ (24 files, 98 errors: 98 E501 + 0 I001)

| File | E501 | Longest | Dominant Pattern |
|------|------|---------|-----------------|
| `test_ipfs_fetch_validation.py` | 11 | 91 | imports, Recipe/serialize_seed calls, monkeypatch lambdas |
| `test_ipfs_reliability.py` | 7 | 88 | imports, monkeypatch.setattr strings, fetch_seed calls |
| `test_container.py` | 6 | 90 | imports, RecipeOp/dict literals, struct calls |
| `test_encryption.py` | 5 | 85 | encode_file kwargs, pytest.raises match strings |
| `test_cli_commands.py` | 5 | 88 | runner.invoke arg lists, EncodeStats constructors |
| `test_signature.py` | 4 | 84 | sign_seed_file call, verify_seed kwargs |
| `test_publish_warning.py` | 4 | 87 | monkeypatch.setattr lambdas, assert strings |
| `test_ml_hooks.py` | 4 | 82 | _fake_request signature, monkeypatch.setattr strings |
| `test_ipfs_optional.py` | 4 | 83 | function signature, subprocess.run call, pytest.skip msg |
| `test_remote_pinning.py` | 3 | 82 | PinningServiceAPIProvider constructor, assert strings |
| `test_oci_oras_bridge.py` | 3 | 84 | monkeypatch.setattr, annotation dicts |
| `test_keygen_cli.py` | 3 | 87 | monkeypatch.setattr lambdas |
| `test_genome_snapshot.py` | 3 | 85 | imports (codec multi-import), encode_file calls |
| `test_perf_gates.py` | 2 | 81 | imports (perf module multi-import) |
| `test_manifest_private.py` | 2 | 85 | encode_file kwargs, ChunkerConfig constructor |
| `test_genes_pack.py` | 2 | 80 | imports (codec multi-import) |
| `test_chunking.py` | 2 | 82 | ChunkerConfig constructor calls |
| `test_verify_strict.py` | 1 | 85 | ChunkerConfig constructor |
| `test_roundtrip.py` | 1 | 88 | (unused lambda or line) |
| `test_prime_verify.py` | 1 | 81 | long assert or string |
| `test_perf.py` | 1 | 85 | imports |
| `test_doctor.py` | 1 | 80 | subprocess.CompletedProcess constructor |
| `test_compat_fixtures.py` | 1 | 81 | f-string in assert |

---

## Modification Pattern Catalog

All modifications are formatting-only. No logic changes.

### Pattern A: Import wrapping
```python
# Before
from helix.codec import decode_file, encode_file, restore_genome, snapshot_genome, verify_seed

# After
from helix.codec import (
    decode_file,
    encode_file,
    restore_genome,
    snapshot_genome,
    verify_seed,
)
```
**Applies to**: test_genome_snapshot, test_genes_pack, test_perf_gates, test_perf, test_ipfs_fetch_validation, test_ipfs_reliability, test_container

### Pattern B: argparse add_argument wrapping
```python
# Before
parser.add_argument("--timeout-s", type=float, default=20.0, help="HTTP timeout seconds")

# After
parser.add_argument(
    "--timeout-s",
    type=float,
    default=20.0,
    help="HTTP timeout seconds",
)
```
**Applies to**: scripts/ml_hooks.py (14 lines), scripts/oras_seed.py, scripts/bench_gate.py

### Pattern C: Constructor / function call wrapping
```python
# Before
recipe = Recipe(hash_table=[chunk_hash], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)])

# After
recipe = Recipe(
    hash_table=[chunk_hash],
    ops=[RecipeOp(opcode=OP_RAW, hash_index=0)],
)
```
**Applies to**: gen_compat_fixtures.py, test_ipfs_fetch_validation.py, test_ipfs_reliability.py, test_container.py, test_cli_commands.py, test_chunking.py, test_manifest_private.py

### Pattern D: monkeypatch.setattr lambda wrapping
```python
# Before
monkeypatch.setattr("helix.cli.publish_seed", lambda _seed, pin=False: "bafyplain")

# After
monkeypatch.setattr(
    "helix.cli.publish_seed",
    lambda _seed, pin=False: "bafyplain",
)
```
**Applies to**: test_publish_warning.py, test_keygen_cli.py, test_ipfs_optional.py, test_ipfs_reliability.py

### Pattern E: Long f-string print wrapping
```python
# Before
print(f"reuse_improvement_bps={report.reuse_improvement_bps} seed_size_ratio={report.seed_size_ratio:.4f}")

# After
print(
    f"reuse_improvement_bps={report.reuse_improvement_bps} "
    f"seed_size_ratio={report.seed_size_ratio:.4f}"
)
```
**Applies to**: scripts/bench_shifted_dedup.py, scripts/bench_gate.py

### Pattern F: Long function signature wrapping
```python
# Before
def test_publish_fetch_if_ipfs_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

# After
def test_publish_fetch_if_ipfs_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
```
**Applies to**: test_ipfs_optional.py, test_ml_hooks.py

### Pattern G: Long assert message / string extraction
```python
# Before
assert digest == entry["seed_sha256"], f"fixture digest drifted: {path.name}"

# After (keep as-is if <= 79, or split)
msg = f"fixture digest drifted: {path.name}"
assert digest == entry["seed_sha256"], msg
```
**Applies to**: test_compat_fixtures.py, test_doctor.py

### Pattern H: json.dumps / long single-expression wrapping
```python
# Before
manifest_path.write_text(json.dumps({"fixtures": metadata}, indent=2, sort_keys=True) + "\n")

# After
content = json.dumps(
    {"fixtures": metadata}, indent=2, sort_keys=True
)
manifest_path.write_text(content + "\n")
```
**Applies to**: scripts/gen_compat_fixtures.py

---

## Step-by-Step Implementation Plan

### Step 1: Auto-fix I001 import sort violations (3 errors)

```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check scripts/ tests/ --select I001 --fix
```

**Files affected**:
- `tests/test_genome_snapshot.py`
- `tests/test_ipfs_fetch_validation.py`
- `tests/test_perf_gates.py`

**Verification**:
```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check scripts/ tests/ --select I001
```
Expected: 0 errors

### Step 2: Fix scripts/bench_gate.py (1 E501)

- Line 11: argparse description -> already wrapped (verify; may be border case at exactly 80 chars)
- Pattern B: wrap add_argument if needed

### Step 3: Fix scripts/bench_shifted_dedup.py (~8 E501)

- Lines 13-17, 19-23, 25-28: f-string print statements
- Pattern E: implicit string concatenation already used; check if individual lines exceed 79

### Step 4: Fix scripts/gen_compat_fixtures.py (3 E501)

- Line 50: Recipe constructor -> Pattern C
- Line 106: json.dumps chain -> Pattern H
- Line 88: signature_key_id str(...) call -> wrap dict entry

### Step 5: Fix scripts/ml_hooks.py (14 E501)

- Lines 22, 25-27, 38-40, 49, 52-56: argparse add_argument -> Pattern B
- Lines 85-86: function signature / or-expression -> Pattern F or variable extraction

### Step 6: Fix scripts/oras_seed.py (6 E501)

- argparse add_argument calls -> Pattern B
- f-string output lines -> Pattern E

### Step 7: Verify scripts/ is clean

```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check scripts/
```
Expected: 0 errors

### Step 8: Fix tests/ E501 -- high-count files first

Process order (descending by error count for maximum impact):

1. **test_ipfs_fetch_validation.py** (11): imports -> Pattern A; Recipe/serialize_seed -> Pattern C; monkeypatch -> Pattern D
2. **test_ipfs_reliability.py** (7): imports -> Pattern A; monkeypatch -> Pattern D; fetch_seed call -> Pattern C
3. **test_container.py** (6): imports (already wrapped); RecipeOp lists -> Pattern C; dict literals -> line break
4. **test_encryption.py** (5): ChunkerConfig -> Pattern C; pytest.raises match -> stays or Pattern C
5. **test_cli_commands.py** (5): runner.invoke arg lists -> Pattern C; EncodeStats -> Pattern C
6. **test_signature.py** (4): sign_seed_file -> Pattern C; verify_seed -> Pattern C
7. **test_publish_warning.py** (4): monkeypatch lambdas -> Pattern D; assert not in -> split
8. **test_ml_hooks.py** (4): function signatures -> Pattern F; monkeypatch -> Pattern D
9. **test_ipfs_optional.py** (4): function signature -> Pattern F; subprocess.run -> Pattern C
10. **test_remote_pinning.py** (3): constructor -> Pattern C; assert strings
11. **test_oci_oras_bridge.py** (3): monkeypatch -> Pattern D; annotation dicts
12. **test_keygen_cli.py** (3): monkeypatch lambdas -> Pattern D
13. **test_genome_snapshot.py** (3): imports -> Pattern A; encode_file -> Pattern C
14. **test_perf_gates.py** (2): imports -> Pattern A
15. **test_manifest_private.py** (2): ChunkerConfig -> Pattern C; encode_file kwargs
16. **test_genes_pack.py** (2): imports -> Pattern A
17. **test_chunking.py** (2): ChunkerConfig -> Pattern C
18. **test_verify_strict.py** (1): ChunkerConfig -> Pattern C
19. **test_roundtrip.py** (1): identify and wrap
20. **test_prime_verify.py** (1): identify and wrap
21. **test_perf.py** (1): imports -> Pattern A
22. **test_doctor.py** (1): subprocess.CompletedProcess -> Pattern C
23. **test_compat_fixtures.py** (1): assert message -> Pattern G

### Step 9: Verify tests/ is clean

```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check tests/
```
Expected: 0 errors

### Step 10: Run full lint and test suite

```bash
# Full lint
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .

# Full test suite
PYTHONPATH=src uv run --no-editable python -m pytest
```

Expected:
- ruff: 0 errors
- pytest: all tests pass (same count as before)

### Step 11: Commit

```bash
git add scripts/ tests/
git commit -m "improve: PEP8 cleanup for scripts/ and tests/ (line-length=79)"
```

Single commit is preferred because:
- All changes are formatting-only (no behavioral changes)
- Matches the pattern of `86898fa` which did all src/ in one commit
- Easier to revert if needed

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test breaks from string splitting | Low | High | Run pytest after every file batch |
| Missed E501 line (still > 79) | Low | Medium | Run ruff check after each step |
| Import reorder breaks runtime | Very Low | High | I001 auto-fix is deterministic; test suite validates |
| Long assert message changes semantics | None | None | String content unchanged, only formatting |
| Accidental logic change in lambda wrapping | Very Low | High | Diff review: no non-whitespace changes except line breaks |

### Safety Guardrails

1. **Before starting**: Record current test count: `pytest --co -q | tail -1`
2. **After I001 auto-fix**: Run full tests immediately
3. **After each directory (scripts/, tests/)**: Run full lint + tests
4. **Final check**: `ruff check .` returns 0 AND `pytest` passes with same test count
5. **Diff review**: `git diff --stat` should show only formatting changes; no line-count reduction beyond import collapsing

---

## Testing Strategy

1. **Pre-change baseline**:
   ```bash
   PYTHONPATH=src uv run --no-editable python -m pytest --tb=no -q 2>&1 | tail -3
   ```
   Record: X passed, Y warnings

2. **After I001 fix** (Step 1):
   ```bash
   PYTHONPATH=src uv run --no-editable python -m pytest --tb=short -q
   ```

3. **After scripts/ complete** (Step 7):
   ```bash
   UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check scripts/
   PYTHONPATH=src uv run --no-editable python -m pytest --tb=short -q
   ```

4. **After tests/ complete** (Step 9):
   ```bash
   UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .
   PYTHONPATH=src uv run --no-editable python -m pytest --tb=short -q
   ```

5. **Final validation** (Step 10):
   - Confirm 0 ruff errors
   - Confirm same test count as baseline
   - Confirm no test failures

---

## Commit Strategy

**Single commit** with message:
```
improve: PEP8 cleanup for scripts/ and tests/ (line-length=79)
```

This mirrors the existing `86898fa` commit for `src/helix/` and completes the line-length=79 migration started in `674da6f`.

If the diff is reviewed and found too large for comfortable review, an alternative 2-commit strategy:
1. `improve: PEP8 cleanup for scripts/ (line-length=79)`
2. `improve: PEP8 cleanup for tests/ (line-length=79)`

---

### Claude Code Workflow

**Category**: CodeQuality
**Size**: M (133 errors across 27 files, formatting-only, ~2-3 hours)

**Workflow Pattern**: `/investigate` -> `/plan` -> `/refactor` -> `/test` -> `/review` -> `/commit`

| Phase | Tool | Action | Notes |
|-------|------|--------|-------|
| 1. Investigate | `/investigate` | (complete) CI failure root cause analysis | Output: `docs/research/ci-lint-failure-investigation.md` |
| 2. Plan | `/plan` | (this document) Implementation plan | Output: `docs/plans/pep8-scripts-tests-cleanup.md` |
| 3. Auto-fix | `/refactor` | `ruff check --fix` for I001 | 3 files, fully automated |
| 4. Manual fix | `/refactor` | E501 fixes: scripts/ then tests/ | Pattern-based, file-by-file |
| 5. Test | `/test` | `pytest` + `ruff check .` | Full suite, zero failures expected |
| 6. Review | `/review` | Verify formatting-only, no logic changes | Diff review |
| 7. Commit | `/commit` | Single conventional commit | `improve: PEP8 cleanup for scripts/ and tests/ (line-length=79)` |

**Execution example**:
```
User: /refactor scripts/ and tests/ PEP8 line-length=79 cleanup per docs/plans/pep8-scripts-tests-cleanup.md
```
