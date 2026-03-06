# Code Review: T-006 — next_action constants

Files reviewed:
- `src/helix/errors.py` (lines 74-125, 14 new ACTION_* constants)
- `src/helix/container.py` (45 raise modifications)
- `src/helix/codec.py` (16 raise modifications)
- `tests/test_container.py` (new `TestNextAction` class)
- `tests/test_genes_pack.py` (2 new tests)
- `tests/test_genome_snapshot.py` (1 new test)

---

## Critical Issues

None found.

---

## Warnings

### W-1: Unreachable guard introduces dead code and misleads `ACTION_REPORT_BUG` usage

**Location:** `container.py:521–525`

```python
if integrity_section_start is None:
    raise SeedFormatError(
        "Integrity section position not found.",
        next_action=ACTION_REGENERATE_SEED,
    )
```

`integrity_section_start` is set in the same loop that sets `integrity_payload`. The guard at line 503–511 already verifies `integrity_payload is not None`, which means the `SECTION_INTEGRITY` branch was hit, so `integrity_section_start` is always set by that point. The None-guard at line 521 is **dead code** and will never fire.

**Impact:** This masks the fact that `ACTION_REPORT_BUG` was originally the right constant here (same pattern as the `encode_recipe` guard at line 122 that uses `ACTION_REPORT_BUG`). The chosen constant `ACTION_REGENERATE_SEED` is misleading for what is effectively a code invariant violation.

**Suggested fix:** Either remove the dead guard, or if it is kept as a defensive assert, use `ACTION_REPORT_BUG` to match the invariant-violation pattern.

---

### W-2: Symmetric dead code for `signature_section_start` in the second branch

**Location:** `container.py:657–661`

```python
if signature_section_start is None:
    raise SeedFormatError(
        "Signature section position not found.",
        next_action=ACTION_REGENERATE_SEED,
    )
```

Inside the `if signature_payload is not None:` block, `signature_section_start` cannot be None because both variables are assigned in the same `elif stype == SECTION_SIGNATURE:` branch. Same dead-code problem as W-1, same wrong constant (`ACTION_REPORT_BUG` would be more correct).

---

### W-3: Inconsistent action choice for "unknown compression at encode time" vs "unknown compression at decode time"

**Location:** `container.py:90–93` (`_compress`, fallthrough) and `container.py:111–114` (`_decompress`, fallthrough)

Both fallthrough raises use `ACTION_REGENERATE_SEED`. However:
- `_compress` is called during **encoding** (writer side). The caller passed an unsupported name string directly; regenerating the seed is not helpful — the problem is the caller's invalid input. `ACTION_CHECK_OPTIONS` (used at line 373 for the same invalid-name scenario in `serialize_seed`) is the right action.
- `_decompress` is called during **decoding** of an existing seed. `ACTION_REGENERATE_SEED` is appropriate there.

The `_compress` fallthrough is unreachable in practice (validated by `serialize_seed` first at line 373 with `ACTION_CHECK_OPTIONS`), but the inconsistency between the two identical-looking code paths warrants documentation or alignment.

---

### W-4: `ACTION_REGENERATE_SEED` applied to integrity-check failures that are indistinguishable from corruption/tampering

**Location:** `container.py:508–511`

```python
raise SeedFormatError(
    "Seed missing required section(s).",
    next_action=ACTION_REGENERATE_SEED,
)
```

A missing required section means the file was either truncated mid-transfer or tampered with, not that the user needs to re-encode. `ACTION_REFETCH_SEED` is the consistent choice used for every other structural truncation/corruption error in the same function (e.g., lines 471, 478, 500). This is the only structural-truncation error in `parse_seed` that diverges to `ACTION_REGENERATE_SEED`.

---

## Suggestions

### S-1: `_compress`/`_decompress` asymmetry: name-based vs id-based interface

**Location:** `container.py:75` vs `container.py:96`

`_compress(data, name: str)` accepts a string name while `_decompress(data, ctype: int)` accepts an integer id. The constant tables `_COMPRESSION_NAME_TO_ID` and `_COMPRESSION_ID_TO_NAME` exist precisely to bridge these. Callers can easily use the wrong form. A unified internal interface (both accept `int`, callers convert once at the boundary) would remove this asymmetry. This is pre-existing but the T-006 changes expose it by adding two parallel raise paths in each function that could be reduced to one if the interface were unified.

---

### S-2: Copy-paste duplication in integrity check raises (6 pairs of CRC/SHA-256 checks)

**Location:** `container.py:547–616`

The 8 integrity-check raises all share the identical pattern: `"<section> <check> mismatch; seed may be corrupted or tampered."` with `next_action=ACTION_REFETCH_SEED`. The string fragments are the only variation. These are correct and consistent after T-006, but a helper like:

```python
def _integrity_mismatch(field: str) -> SeedFormatError:
    return SeedFormatError(
        f"{field} mismatch; seed may be corrupted or tampered.",
        next_action=ACTION_REFETCH_SEED,
    )
```

would eliminate 8 repetitive raise blocks. Out of scope for T-006 but worth a follow-up ticket.

---

### S-3: `TestNextAction` test for `integrity_mismatch_has_refetch_action` duplicates `test_seed_integrity_detects_manifest_sha256_mismatch`

**Location:** `tests/test_container.py:73–104` vs `tests/test_container.py:148–172`

Both tests tamper with `manifest_sha256` in the integrity section and expect `SeedFormatError`. The older test checks `match="Manifest SHA-256 mismatch"`. The new `TestNextAction` test checks `.next_action == ACTION_REFETCH_SEED`. The setup (recipe, manifest, `serialize_seed`, `_tamper_integrity_field`) is copy-pasted. Consider merging: add a `next_action` assertion to the existing test rather than duplicating the full fixture setup.

---

### S-4: `test_invalid_magic_has_verify_action` passes a blob too short to contain a valid header

**Location:** `tests/test_container.py:142–146`

```python
blob = b"XXXX" + b"\x00" * 20
```

The blob is 24 bytes. `parse_seed` first checks `len(data) < 8` (passes), then checks `magic != MAGIC` (fails and raises with `ACTION_VERIFY_SEED`). This works, but the test name says "invalid magic" while the choice of `ACTION_VERIFY_SEED` vs `ACTION_REFETCH_SEED` depends on whether the seed is structurally intact or network-truncated. The test implicitly relies on the magic check firing before the length check for sections — the assertion is valid but the blob construction is fragile (removing bytes could accidentally trigger the "too short" path instead, changing the expected action). A comment explaining the intent would prevent confusion.

---

### S-5: Missing test for `ACTION_REGENERATE_SEED` path

**Location:** `tests/test_container.py`, `TestNextAction`

The 4 tests in `TestNextAction` cover `ACTION_REFETCH_SEED` (2×) and `ACTION_VERIFY_SEED` and `ACTION_VERIFY_ENCRYPTION`. No test exercises the `ACTION_REGENERATE_SEED` path (e.g., `"Seed missing required section(s)."` at container.py:508 or `"Unknown recipe opcode"` at container.py:161). The `ACTION_REPORT_BUG` path (`encode_recipe` with wrong-length digest, container.py:122) is also untested.

---

### S-6: `ACTION_VERIFY_SNAPSHOT` test uses a 14-byte blob that hits the magic check, not the length check

**Location:** `tests/test_genome_snapshot.py:106–116`

```python
bad_snap.write_bytes(b"XXXX" + b"\x00" * 10)
```

The blob is 14 bytes, exactly the header size. `restore_genome` reads 14 bytes successfully, then checks `magic != GENOME_SNAPSHOT_MAGIC`. This correctly fires the magic-mismatch raise. However the 10 zero bytes also set `version=0` and `chunk_count=0`, so if the magic check were accidentally removed the loop would not run and no error would be raised. A blob that is clearly too short (e.g., 4 bytes) would make the failure mode unambiguous.

---

## Summary table

| ID  | Severity   | File            | Line(s)   | Issue                                                               |
|-----|------------|-----------------|-----------|---------------------------------------------------------------------|
| W-1 | Warning    | container.py    | 521–525   | Dead guard, wrong constant (`ACTION_REGENERATE_SEED` vs `ACTION_REPORT_BUG`) |
| W-2 | Warning    | container.py    | 657–661   | Same dead guard in signature branch                                |
| W-3 | Warning    | container.py    | 90–93     | `_compress` fallthrough uses `ACTION_REGENERATE_SEED`; should be `ACTION_CHECK_OPTIONS` |
| W-4 | Warning    | container.py    | 508–511   | "Seed missing required section(s)" uses `ACTION_REGENERATE_SEED` inconsistently with other truncation errors |
| S-1 | Suggestion | container.py    | 75, 96    | Name/id interface asymmetry between `_compress` and `_decompress` |
| S-2 | Suggestion | container.py    | 547–616   | 8 copy-paste integrity-mismatch raises; extract helper             |
| S-3 | Suggestion | test_container  | 148–172   | New integrity-mismatch test duplicates existing fixture setup      |
| S-4 | Suggestion | test_container  | 142–146   | Magic-check test blob construction fragile; add comment            |
| S-5 | Suggestion | test_container  | 134–193   | `ACTION_REGENERATE_SEED` and `ACTION_REPORT_BUG` paths untested    |
| S-6 | Suggestion | test_genome_snapshot | 106–116 | Bad-magic snapshot blob construction fragile                   |
