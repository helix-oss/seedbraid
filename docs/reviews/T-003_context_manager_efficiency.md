# T-003 Context Manager Efficiency Review

**Files reviewed**
- `src/helix/storage.py`
- `src/helix/codec.py`
- `tests/test_genome_snapshot.py`

---

## 1. Key Question: `decode_file()` — genome lifetime vs SHA-256 check

**Verdict: CORRECT. The genome is released before SHA-256 verification.**

```python
# codec.py lines 213-226
with open_genome(genome_path) as genome:      # genome open
    with out_path.open("wb") as out:
        for op in seed.recipe.ops:
            chunk = _resolve_chunk(op, ...)
            out.write(chunk)
            h.update(chunk)
# <-- genome.close() called here via __exit__ (line 220)

actual = h.hexdigest()                        # SHA-256 check happens AFTER close
expected = seed.manifest.get("source_sha256")
if expected and expected != actual:
    raise DecodeError(...)
```

The `with open_genome(genome_path) as genome:` block ends at line 219 (before `actual = h.hexdigest()`), so `__exit__` → `close()` fires before the SHA-256 comparison. This matches the semantics of the original `try/finally: genome.close()` pattern.

---

## 2. Unnecessary Computation in the Context Manager

**Verdict: None introduced.**

`SQLiteGenome.__enter__` (storage.py line 86) does only `return self` — zero overhead. `__exit__` delegates to `self.close()` which calls `self.conn.close()` — identical to what the old `try/finally` blocks did. No new allocations, no extra SQL, no branching.

The `GenomeStorage` Protocol's `__enter__`/`__exit__` stubs (lines 21-28) are declaration-only and carry no runtime cost.

---

## 3. Resource Lifetime Analysis per Function

| Function | Genome held for | Notes |
|---|---|---|
| `encode_file()` | Entire chunking + `write_seed()` call (lines 86-171) | **Warning — see §5** |
| `decode_file()` | Chunk resolution + file write only; released before SHA check | Correct |
| `verify_seed()` | Signature check + chunk walk + optional strict re-scan | Necessary; all work needs genome |
| `prime_genome()` | Full directory scan and put_chunk loop | Necessary |
| `snapshot_genome()` | `count_chunks()` + `iter_chunks()` streaming loop | Correct |
| `restore_genome()` | Full snapshot read + `put_chunk` loop | Correct |
| `export_genes()` | Full hash-table scan with `get_chunk` | Correct |
| `import_genes()` | Full pack read + `put_chunk` loop | Correct |

---

## 4. Warning: `encode_file()` — genome held across `write_seed()` + `sha256_file()`

`encode_file()` keeps the genome open from line 86 through line 171, which includes:

- `write_seed()` call (line 163) — serialises the container, potentially slow for large payloads
- `sha256_file(in_path)` call (line 143) — reads the full input file from disk

Neither of these operations uses `genome`. The genome could be closed immediately after the chunking loop completes (after line 117). Holding it open through `write_seed` and `sha256_file` is unnecessary.

**Impact**: SQLite WAL lock / file descriptor held longer than needed. On slow storage or large files this delays other processes from opening the same genome. Low severity in typical single-process usage, but worth noting.

**Suggested fix** (out of scope for this ticket — research only):
```python
with open_genome(genome_path) as genome:
    # ... chunking loop only ...
    pass  # genome closed here

# then build manifest + write_seed outside the with block
```

This would require extracting the `stats` / `recipe` construction before the `with` exits.

---

## 5. TOCTOU Patterns

**Verdict: One pre-existing pattern, not introduced by this diff.**

`storage.py` line 34: `self.path.parent.mkdir(parents=True, exist_ok=True)` followed immediately by `sqlite3.connect(self.path)`. The `exist_ok=True` flag prevents the race from raising; `sqlite3.connect` creates the file atomically if absent. No TOCTOU window is opened.

`resolve_genome_db_path()` (lines 98-102) checks `p.suffix` on the path string — purely string inspection, no filesystem access, no TOCTOU.

No new TOCTOU patterns were introduced by the context manager conversion.

---

## 6. Memory — Unbounded Data Structures

**Verdict: Two pre-existing issues, not introduced by this diff.**

### 6a. `encode_file()` — `hash_to_index`, `hash_table`, `raw_payloads` (lines 76-79)

All three dicts/lists grow proportionally to the number of unique chunks in the input file. For a 10 GB input with avg 4 KB chunks this is ~2.5 M entries. `raw_payloads` additionally stores chunk bytes (up to `max_size` each) for every unique portable chunk. This can reach hundreds of MB.

This is a **pre-existing** design constraint (streaming chunks but accumulating hash metadata). Not introduced by the context manager change.

### 6b. `verify_seed()` — `missing: list[str]` (line 239)

Accumulates one 64-char hex string per missing chunk. For a severely corrupt seed with millions of ops this could grow large. Pre-existing.

---

## 7. Hot-Path Bloat

**Verdict: None introduced.**

The critical paths are `encode_file` (chunking loop) and `decode_file` (op resolution loop). The context manager wraps the entire function body in both cases — it adds exactly two function calls (`__enter__` returning `self`, `__exit__` calling `conn.close()`) at setup/teardown, not inside any loop. Zero per-iteration overhead.

---

## 8. `__exit__` Does Not Suppress Exceptions

`SQLiteGenome.__exit__` returns `None` (implicitly), which is falsy — exceptions propagate normally. This is correct behaviour; suppressing would hide decode/encode errors.

---

## 9. Test File — `test_genome_snapshot.py`

Lines 79-85 use two standalone `with open_genome(...) as ...:` blocks for `count_chunks()` queries around `snapshot_genome` / `restore_genome`. Each opens and closes a separate connection — correct and minimal. No issues.

---

## Summary

| # | Severity | Location | Issue |
|---|---|---|---|
| 1 | Warning | `codec.py:86-171` `encode_file()` | Genome held open across `write_seed()` + `sha256_file()` — unnecessary lock extension |
| 2 | Suggestion | `codec.py:76-79` `encode_file()` | `hash_to_index`, `hash_table`, `raw_payloads` are unbounded in memory (pre-existing) |
| 3 | Suggestion | `codec.py:239` `verify_seed()` | `missing` list unbounded for corrupt seeds (pre-existing) |

**The primary question is answered**: `decode_file()` correctly releases the genome before SHA-256 verification, matching the original `try/finally` semantics exactly.
