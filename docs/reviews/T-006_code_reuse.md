# T-006 Code Reuse Review

Date: 2026-03-07
Scope: errors.py ACTION_* constants, container.py, codec.py, ipfs.py, pinning.py, mlhooks.py, oci.py, diagnostics.py, tests/

---

## Finding 1 — Duplicate inline string: "Install Kubo and verify with `ipfs --version`."

**Location**: `src/helix/ipfs.py:30` and `src/helix/diagnostics.py:69`

**Issue**: The exact string `"Install Kubo and verify with \`ipfs --version\`."` is hardcoded in
both `ipfs.py` (as a `next_action` on an `ExternalToolError`) and `diagnostics.py` (as a
`next_action` on a `DoctorCheck`). T-006 introduced `ACTION_*` constants in `errors.py` but none
covers this IPFS-specific string. The two sites are now duplicated inline text — not covered by
any constant and not consistent with the pattern adopted for `container.py`/`codec.py`.

**Suggested fix**: Add `ACTION_INSTALL_KUBO = "Install Kubo and verify with \`ipfs --version\`."` to
`errors.py` and replace both inline strings. If `diagnostics.py`'s `DoctorCheck.next_action` field
should not depend on `errors.py`, the constant can live in a shared location (e.g., `errors.py` is
already imported by `ipfs.py`; `diagnostics.py` does not currently import it but can).
Alternatively, document that `diagnostics.py` intentionally stays independent, making this a
conscious divergence rather than accidental duplication.

---

## Finding 2 — Pattern divergence: ipfs.py / pinning.py / mlhooks.py / oci.py use inline strings; container.py / codec.py use ACTION_* constants

**Location**: All `next_action=` sites in `src/helix/ipfs.py`, `src/helix/pinning.py`,
`src/helix/mlhooks.py`, `src/helix/oci.py` (approximately 30+ raise sites)

**Issue**: T-006 introduces a two-tier system:
- `container.py` and `codec.py`: use named `ACTION_*` constants from `errors.py`.
- `ipfs.py`, `pinning.py`, `mlhooks.py`, `oci.py`: all use inline string literals.

The `ACTION_*` constants are defined in `errors.py` and are re-exported via its public namespace,
so they are accessible to all modules. However, none of the pre-existing files (`ipfs.py`,
`pinning.py`, `mlhooks.py`, `oci.py`, `diagnostics.py`) were updated to use constants for the
strings they already had. This creates an asymmetry: two modules use constants, five modules use
inline strings. There is no comment, docstring, or plan note explaining this as intentional.

Notable cases where the inline strings in the older modules semantically overlap with new constants:
- `ipfs.py:153` — `"Use \`--retries\` with value >= 1."` vs `ACTION_CHECK_OPTIONS` =
  `"Check command-line options and retry."` (related but distinct)
- `ipfs.py:59` — `"Ensure IPFS daemon is running and retry publish."` — no constant equivalent
- `oci.py:26` — `"Install ORAS and verify with \`oras version\`."` — no constant equivalent

These are not textual duplicates of existing constants, but they represent the same category of
guidance (check options, install tool) without a shared constant.

**Suggested fix**: Either (a) accept inline strings as the pattern for `ExternalToolError` in
tool-specific modules (they are context-specific and not reused across modules), and document this
explicitly in `errors.py` or `AGENTS.md`; or (b) extend `ACTION_*` constants to cover the common
tool-related patterns used across `ipfs.py`, `pinning.py`, `mlhooks.py`, `oci.py`. Option (a) is
lower risk and is consistent with how these files already existed before T-006.

---

## Finding 3 — diagnostics.py zstd string duplicates ACTION_INSTALL_ZSTD intent but not text

**Location**: `src/helix/diagnostics.py:190-191`

**Issue**: `diagnostics.py` contains:
```
"Run `uv sync --extra zstd`"
" to enable --compression zstd."
```
while `errors.py` defines:
```python
ACTION_INSTALL_ZSTD = (
    "Run `uv sync --extra zstd`"
    " to install zstandard."
)
```

The first line `"Run \`uv sync --extra zstd\`"` is identical. The second line differs:
`"to enable --compression zstd."` vs `"to install zstandard."`. These are semantically equivalent
guidance pointing users to the same command. Having two slightly different wordings for the same
action is a consistency issue. `diagnostics.py` does not import from `errors.py` currently.

**Suggested fix**: Import `ACTION_INSTALL_ZSTD` from `errors.py` in `diagnostics.py` and use it
for the `DoctorCheck.next_action` field, or align the wording of one to match the other. If
`diagnostics.py` must stay independent (it only imports `ExternalToolError` and `HelixError`
today), at minimum align the string text.

---

## Finding 4 — No duplication in test helper functions

**Location**: `tests/test_container.py`, `tests/test_genes_pack.py`, `tests/test_genome_snapshot.py`

**Issue**: None. The new test helper `_tamper_integrity_field` in `test_container.py:107-131` is
unique — no equivalent exists elsewhere in the test suite. The `TestNextAction` class tests and
the standalone `test_import_genes_*` / `test_restore_bad_magic_*` functions do not duplicate
existing helpers. Confirmed by grepping `next_action` across all test files.

**Suggested fix**: False positive — no action needed.

---

## Finding 5 — ACTION_CHECK_OPTIONS used for a serialization/compression error (semantic mismatch)

**Location**: `src/helix/container.py` (plan table row: `L308`, `ACTION_CHECK_OPTIONS`)

**Issue**: `ACTION_CHECK_OPTIONS = "Check command-line options and retry."` is assigned to
`serialize_seed` compression errors (unsupported `manifest_compression` value passed
programmatically). This string implies the user passed a bad CLI flag, but the error can also be
raised by internal callers passing invalid arguments. `ACTION_CHECK_OPTIONS` is the only constant
whose name is CLI-framing. This is a minor semantic divergence but not a code reuse problem per se.

**Suggested fix**: Consider adding `ACTION_CHECK_ARGUMENTS = "Check the provided argument value."` or
reuse `ACTION_REPORT_BUG` for internal-only callers. Low priority; not a reuse defect.

---

## Summary

| # | File(s) | Issue Type | Severity |
|---|---------|-----------|----------|
| 1 | `ipfs.py:30`, `diagnostics.py:69` | Exact string duplicated, not covered by constant | Warning |
| 2 | `ipfs.py`, `pinning.py`, `mlhooks.py`, `oci.py` vs `container.py`, `codec.py` | Pattern divergence: inline vs constants | Warning |
| 3 | `diagnostics.py:190`, `errors.py:95-98` | Near-duplicate string, different wording, same intent | Warning |
| 4 | `tests/` | No duplication in test helpers | False positive |
| 5 | `container.py` (serialize compression error) | Semantic mismatch of ACTION_CHECK_OPTIONS | Suggestion |
