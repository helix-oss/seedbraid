# Code Review: T-003 Context Manager Implementation — Reuse Opportunities

Date: 2026-03-06
Scope: `src/helix/storage.py`, `src/helix/codec.py`, `tests/test_genome_snapshot.py`

---

## 1. `__enter__`/`__exit__` Implementation in `SQLiteGenome`

### Pattern Uniqueness

The `SQLiteGenome.__enter__`/`__exit__` pair is the **only** context manager implementation
in the production source tree (`src/helix/`). No existing utility in the codebase could have
been reused or composed instead.

Two test-only context manager stubs exist:
- `tests/test_remote_pinning.py` — `_Resp.__enter__`/`__exit__` (mock HTTP response)
- `tests/test_ipfs_reliability.py` — `_Resp.__enter__`/`__exit__` (identical mock, inline class)

Both are unrelated response mocks, not storage abstractions. They share the same untyped
`(self, exc_type, exc, tb)` signature with `# noqa: ANN001, ANN201` suppressions. This is
intentionally lightweight test code, not a pattern applicable to production.

### Missed Alternative: `contextlib.closing`

`contextlib.closing` wraps any object with a `.close()` method into a context manager. Since
`SQLiteGenome` already had `close()` before this diff, the following would have been
functionally equivalent **without adding `__enter__`/`__exit__`** to the class:

```python
# codec.py — prior to this diff, using contextlib.closing:
from contextlib import closing
with closing(open_genome(genome_path)) as genome:
    ...
```

However, adding `__enter__`/`__exit__` directly to `SQLiteGenome` is the **better design**
because:
1. `open_genome()` returns a `SQLiteGenome` that callers expect to be a context manager.
2. Updating the `GenomeStorage` Protocol to include context manager methods ensures any future
   alternative storage backend (e.g., an in-memory or remote genome) must implement the same
   lifecycle interface.
3. `contextlib.closing` would have required every call site to import `contextlib`, increasing
   coupling in `codec.py`.

**Verdict**: No missed reuse opportunity. The implementation is the correct approach.

---

## 2. `import types` — Uniqueness in Codebase

`import types` (stdlib `types` module, for `types.TracebackType`) is used **only** in
`src/helix/storage.py`. No other source file uses this import.

### Is `types.TracebackType` Necessary?

`types.TracebackType` is the canonical type annotation for the `tb` argument of `__exit__`.
It is the standard approach in typed Python code when `from __future__ import annotations`
is active (which it is in `storage.py`), because the annotation is evaluated lazily.

An alternative available since Python 3.11 is:
```python
# Using collections.abc or builtins — not available for TracebackType
```
There is no alternative to `types.TracebackType` for this annotation. The stdlib `types`
module import is correct and minimal.

**Verdict**: No duplication or reuse opportunity. Unique and necessary.

---

## 3. `Self` Import — Consistency Check

`Self` is imported from `typing` in `storage.py`:
```python
from typing import Protocol, Self
```

Codebase-wide `Self` usage:
- `src/helix/storage.py` — the only production file using `Self`
- `docs/plans/T-003_plan.md` — planning doc reference
- `docs/research/T-003_investigation.md` — research doc reference

No other production module uses `Self`. The import is consistent with the existing
`from typing import Protocol` pattern in `pinning.py` (same stdlib, same `from typing import`
style). There is no existing utility to replace it.

**Verdict**: Consistent with project style. No reuse opportunity.

---

## 4. Remaining `try/finally: *.close()` Patterns

### In `src/helix/`

After the diff, no `try/finally: genome.close()` patterns remain in `src/helix/codec.py`.
A thorough multiline grep confirmed zero remaining `try: ... finally: ... .close()` chains
anywhere in `src/helix/`.

### In `tests/`

No test files contain `try/finally: *.close()` patterns. The two converted locations in
`test_genome_snapshot.py` (lines 79 and 84) are now `with open_genome(...) as ...:`.

### Remaining `try:` Blocks in `codec.py` (Not Missed)

`codec.py` retains two `try:` blocks after the diff:
- `snapshot_genome()` line 403: `try: ... with out_path.open("wb")` — catches `OSError`, not
  a resource leak pattern. Correctly left as-is.
- `restore_genome()` line 435: `try: ... with snapshot_path.open("rb")` — same, catches
  `OSError`. Correctly left as-is.

These are error-handling try/except blocks, not resource management try/finally blocks. They
were not candidates for the `with open_genome(...)` conversion.

---

## 5. Protocol Consistency: `GenomeStorage` vs `RemotePinProvider`

`pinning.py` defines `RemotePinProvider(Protocol)` without context manager methods. This is
appropriate because `RemotePinProvider` is a stateless service interface (HTTP-based), not a
resource-holding connection object. The asymmetry is intentional and correct.

`GenomeStorage(Protocol)` now correctly includes `__enter__`/`__exit__`, making it a proper
resource-owning protocol. The `Self` return type on `__enter__` in the Protocol is sound:
it ensures structural subtype checking remains valid for any implementing class.

---

## 6. Minor Issues Found

### Warning: Protocol `__enter__` Returns `Self`, Concrete Class Returns `SQLiteGenome`

In `storage.py`:
- Protocol: `def __enter__(self) -> Self: ...`
- Concrete: `def __enter__(self) -> SQLiteGenome:`

This is a minor type narrowing asymmetry. `SQLiteGenome` satisfies `GenomeStorage[Protocol]`
here because `SQLiteGenome` is a concrete subtype of `Self` when `Self` is resolved against
`SQLiteGenome`. However, for strict mypy structural checking, the concrete return type should
also use `Self`:

```python
def __enter__(self) -> Self:
    return self
```

This requires adding `Self` to the `SQLiteGenome` class's own imports — which it already has
access to since `Self` is imported at module level. This is a low-priority inconsistency;
mypy with `--strict` may emit a warning depending on configuration.

**Severity**: Suggestion

### Suggestion: Duplicate `_Resp` Mock in Test Files

`tests/test_remote_pinning.py` and `tests/test_ipfs_reliability.py` both define a `_Resp`
class with identical `__enter__`/`__exit__` + `read()` structure. The test in
`test_ipfs_reliability.py` even defines it as an inline class inside a test function.

These could be consolidated into a shared `tests/conftest.py` fixture or a `tests/_helpers.py`
module. This is unrelated to the diff but was found during the search.

**Severity**: Suggestion (out of diff scope)

---

## Summary

| Area | Finding | Severity |
|---|---|---|
| `SQLiteGenome.__enter__`/`__exit__` | No missed reuse; `contextlib.closing` was an option but direct implementation is superior | None |
| `import types` | Unique in codebase; necessary for `types.TracebackType` | None |
| `Self` import | Consistent with project `from typing import` style | None |
| Remaining `try/finally` close patterns | Zero remaining after diff | None |
| Protocol vs concrete `__enter__` return type | `Self` in Protocol but concrete type in class | Suggestion |
| Duplicate `_Resp` test mock | Two test files define identical HTTP response mocks | Suggestion |
