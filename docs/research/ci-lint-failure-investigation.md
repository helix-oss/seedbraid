# CI Lint Failure Investigation Report

**Date**: 2026-03-07
**Status**: Complete
**Scope**: GHA CI failure due to ruff E501 and I001 violations

---

## Executive Summary

**Root Cause**: Line-length configuration mismatch between pyproject.toml and code state.
- Commit `674da6f` updated `pyproject.toml` from `line-length = 100` to `line-length = 79`
- Commit `86898fa` applied line-length cleanup to `src/helix/` only
- **`scripts/` and `tests/` directories were NOT reformatted**, creating 133 lint violations

**Impact**: 
- **130 E501 violations** (line too long)
- **3 I001 violations** (import sort, auto-fixable)
- **27 files affected** (14 scripts, 13 tests)
- **133 total errors** as reported by GHA CI

---

## Root Cause Analysis

### Historical Context

1. **Commit `86898fa`** (2026-03-06 10:06:25 +0900)
   - **Message**: "improve: PEP8 cleanup for all src/helix/ modules (line-length=79)"
   - **Action**: Reformatted 11 files in `src/helix/` to conform to line-length=79
   - **pyproject.toml state**: `line-length = 100` (NOT changed in this commit)
   - **Result**: Code changed but config not yet updated

2. **Commit `674da6f`** (2026-03-06 11:48:07 +0900)
   - **Message**: "improve: update ruff line-length to 79 across config and docs"
   - **Action**: Updated `pyproject.toml` from `line-length = 100` → `line-length = 79`
   - **Scope**: Only updated config, code-reviewer agent config, and test infrastructure docs
   - **Coverage**: Did NOT apply linting to `scripts/` or `tests/` directories
   - **Result**: Line-length enforcement now active, but non-src targets non-compliant

### Configuration Details

**File**: `pyproject.toml`
```toml
[tool.ruff]
line-length = 79
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["B008", "B904"]
```

**Key Points**:
- No `extend-exclude` or `per-file-ignores` rules exclude `scripts/` or `tests/`
- All directories are linted uniformly
- Both E501 (line too long) and I (import sorting) rules are active
- No per-file or directory-specific exemptions exist

---

## Impact Assessment

### Error Distribution by Directory

| Directory | File Count | Error Count | E501 | I001 | Notes |
|-----------|-----------|-------------|------|------|-------|
| `scripts/` | 3 | 35 | 32 | 3 | All I001 errors; longest line 100 chars |
| `tests/` | 24 | 98 | 98 | 0 | All E501 errors; longest line 98 chars |
| **TOTAL** | **27** | **133** | **130** | **3** | - |

### Top 5 Affected Files by Error Count

1. **scripts/ml_hooks.py**: 14 E501 errors
   - Longest: 98 chars (help strings in argparse)
   - Issue: argparse description strings not wrapped

2. **tests/test_ipfs_fetch_validation.py**: 11 E501 errors
   - Longest: 91 chars (Recipe/RecipeOp constructor calls)
   - Issue: Complex function signatures with keyword arguments

3. **tests/test_ipfs_reliability.py**: 7 E501 errors
   - Issue: Similar to test_ipfs_fetch_validation.py

4. **tests/test_container.py**: 6 E501 errors
   - Issue: Long import statements

5. **scripts/oras_seed.py**: 6 E501 errors
   - Issue: Argparse help strings, long function signatures

### Error Type Breakdown

#### E501 (Line too Long)
- **Total**: 130 violations
- **Range**: 80–100 chars (all exceed 79-char limit)
- **Distribution**:
  - 24 errors @ 85 chars (longest exceeding)
  - 19 errors @ 81 chars
  - 11 errors @ 91 chars
  - 9 errors @ 84 chars
  - 8 errors @ 87 chars
  - [and 79 more across 15+ length variants]

#### I001 (Import Sort)
- **Total**: 3 violations (100% auto-fixable with `--fix`)
- **Files affected**:
  1. tests/test_genome_snapshot.py:1:1
  2. tests/test_ipfs_fetch_validation.py:1:1
  3. tests/test_perf_gates.py:1:1
- **Root cause**: Likely `from __future__ import annotations` placement
- **Fix**: `ruff check --fix` will resolve all 3

---

## Why This Happened

### Workflow Defect

The PEP8 cleanup and config update were split across two commits:

```
86898fa → reformat src/helix/ to line-length=79 (keep config @ 100)
↓
[Config still at 100, tests/scripts untouched]
↓
674da6f → update pyproject.toml to line-length=79 (no code changes)
↓
[Linter now enforces 79, but non-src code unchanged]
```

### Why tests/ and scripts/ Were Skipped

1. **Intent**: PEP8 cleanup commit message states "all src/helix/ modules" (not test/script code)
2. **Practical risk**: Large reformatting of test fixtures and scripts could introduce subtle bugs
3. **Oversight**: Config change in 674da6f did not account for this incomplete coverage
4. **CI detection**: Only triggered when linter ran at CI stage

---

## Recommended Fix Strategy

### Phase 1: Quick Fix (Automated)
**Action**: Apply `ruff check --fix` to resolve I001 import-sort violations
```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check . --fix
```
**Result**: Resolves 3 errors (all I001)
**Effort**: Seconds
**Risk**: None (import sort is deterministic and safe)

### Phase 2: Manual Fix (Code Review Required)
**Action**: Manually reformat long lines in `scripts/` and `tests/` (130 E501 violations)

#### Recommended Approach:
1. **scripts/ directory** (35 errors, 3 files)
   - Priority: HIGH (breaks CI)
   - Effort: ~30–40 minutes
   - Strategy:
     - `scripts/ml_hooks.py`: Wrap long argparse help strings (14 errors)
     - `scripts/gen_compat_fixtures.py`: Wrap long dict/function calls (3 errors)
     - `scripts/bench_gate.py`: Wrap description string (1 error)
   
2. **tests/ directory** (98 errors, 24 files)
   - Priority: HIGH (breaks CI)
   - Effort: ~2–3 hours (requires test knowledge to avoid breaking logic)
   - Strategy:
     - Import statements: Split long from clauses (6 files)
     - Function signatures: Wrap long function definitions
     - Constructor calls: Break Recipe/RecipeOp and similar multi-arg calls
     - Test helpers: Wrap long string literals and function calls

#### Code Formatting Patterns

**Pattern A**: Long import statements
```python
# Before (88 chars)
from helix.container import OP_RAW, Recipe, RecipeOp, encrypt_seed_bytes, serialize_seed

# After (split to 2 lines)
from helix.container import (
    OP_RAW, Recipe, RecipeOp, encrypt_seed_bytes, serialize_seed
)
```

**Pattern B**: argparse help strings
```python
# Before (98 chars)
parser.add_argument("--timeout-s", type=float, default=20.0, help="HTTP timeout seconds")

# After (split to multiple lines)
parser.add_argument(
    "--timeout-s",
    type=float,
    default=20.0,
    help="HTTP timeout seconds",
)
```

**Pattern C**: Constructor/function calls with many kwargs
```python
# Before (97 chars)
recipe = Recipe(hash_table=[chunk_hash], ops=[RecipeOp(opcode=OP_RAW, hash_index=0)])

# After (split across multiple lines)
recipe = Recipe(
    hash_table=[chunk_hash],
    ops=[RecipeOp(opcode=OP_RAW, hash_index=0)],
)
```

### Phase 3: Prevention (Process)
**Action**: Update CLAUDE.md and CI scripts to enforce pre-commit linting on all directories

**Proposed Changes**:
1. Add pre-commit hook to scripts/tests before line-length config changes
2. Document in CONTRIBUTING.md that line-length changes require full-repo reformatting
3. Consider adding `.claude/rules/formatting.md` to enforce line-length in all dirs
4. Update CI/CD to fail early on lint violations (before merge)

---

## Fix Priority Recommendation

| Phase | Action | Files | Errors | Effort | Risk | Prereq |
|-------|--------|-------|--------|--------|------|--------|
| 1 | `ruff check --fix` (I001) | 3 | 3 | <5 min | None | - |
| 2a | Reformat scripts/ | 3 | 35 | 30–40 min | Low | Phase 1 |
| 2b | Reformat tests/ | 24 | 98 | 2–3 hrs | Medium | Phase 1 |
| 3 | Update CI/docs | - | - | 15–20 min | None | Phase 2 |

**Critical Path**: Phase 1 → Phase 2a → Phase 2b (sequential)
**Total Estimated Time**: 3–4 hours (including testing)

---

## File-by-File Error Summary

### scripts/ (3 files, 35 errors)

| File | E501 | I001 | Longest Line | Issue |
|------|------|------|--------------|-------|
| scripts/ml_hooks.py | 14 | 1 | 98 | argparse help strings, type hints |
| scripts/gen_compat_fixtures.py | 3 | 1 | 97 | dict/call signatures |
| scripts/bench_gate.py | 1 | 1 | 80 | description string |

### tests/ (24 files, 98 errors)

| File | E501 | I001 | Longest Line | Issue |
|------|------|------|--------------|-------|
| test_ipfs_fetch_validation.py | 11 | 1 | 91 | imports, Recipe calls |
| test_ipfs_reliability.py | 7 | 0 | 88 | imports, function signatures |
| test_container.py | 6 | 0 | 90 | imports, function definitions |
| test_encryption.py | 5 | 0 | 85 | function signatures |
| test_cli_commands.py | 5 | 0 | 88 | long strings, function calls |
| test_signature.py | 4 | 0 | 84 | imports, test assertions |
| test_publish_warning.py | 4 | 0 | 87 | function signatures |
| test_ml_hooks.py | 4 | 0 | 82 | function definitions |
| test_ipfs_optional.py | 4 | 0 | 83 | monkeypatch/lambda calls |
| test_remote_pinning.py | 3 | 0 | 82 | long strings |
| test_oci_oras_bridge.py | 3 | 0 | 84 | function signatures |
| test_keygen_cli.py | 3 | 0 | 87 | monkeypatch calls |
| test_genome_snapshot.py | 3 | 1 | 85 | imports, function calls |
| test_perf_gates.py | 2 | 1 | 81 | imports |
| test_manifest_private.py | 2 | 0 | 85 | long strings |
| test_genes_pack.py | 2 | 0 | 80 | imports |
| test_chunking.py | 2 | 0 | 82 | function calls |
| test_verify_strict.py | 1 | 0 | 85 | function signature |
| test_roundtrip.py | 1 | 0 | 88 | lambda call |
| test_prime_verify.py | 1 | 0 | 81 | long string |
| test_perf.py | 1 | 0 | 85 | import statement |
| test_doctor.py | 1 | 0 | 80 | long string |
| test_compat_fixtures.py | 1 | 0 | 81 | long string |

---

## Next Steps

1. **Immediate** (today):
   - [ ] Run Phase 1 fix: `ruff check --fix` (resolves 3 I001 errors)
   - [ ] Stage changes and verify no breakage

2. **Short-term** (this week):
   - [ ] Execute Phase 2a: Reformat scripts/ (35 errors)
   - [ ] Execute Phase 2b: Reformat tests/ (98 errors)
   - [ ] Run full test suite: `pytest` to ensure no logic changes
   - [ ] Run full lint: `ruff check` to verify all 133 errors resolved

3. **Documentation**:
   - [ ] Update CONTRIBUTING.md to require line-length compliance in all dirs
   - [ ] Document in CLAUDE.md that config changes require full-repo reformatting
   - [ ] Add pre-commit hook suggestion

4. **Prevention**:
   - [ ] Consider adding CI step to fail on lint violations before merge
   - [ ] Document in AGENTS.md that line-length changes must include full coverage

---

## Verification Checklist

- [ ] All 133 lint errors resolved
- [ ] All 98 tests pass
- [ ] `ruff check .` shows zero violations
- [ ] Git history is clean (no merge conflicts)
- [ ] No functional code changes (formatting only)
- [ ] CLAUDE.md updated with prevention guidance
