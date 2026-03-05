# CLI.py Coverage Gap Analysis

## Summary
- **Current Coverage**: 177 lines covered / 261 total = 53%
- **Missing Lines**: 35-39, 83-114, 129-138, 167-197, 210-224, 284-286, 289-290, 304-305, 338-342, 350-351, 419, 433-434, 501-517, 527-531, 542-546, 555-559, 573-577, 590-591
- **Total Lines Missing**: 84 lines across 18 distinct gaps

---

## Detailed Gap Analysis

### Gap 1: Lines 35-39 (_cfg function validation)
**Function**: `_cfg()` - ChunkerConfig parameter validator
**Location**: lines 34-44

```python
def _cfg(avg: int, min_size: int, max_size: int, window_size: int = 64) -> ChunkerConfig:
    if min_size <= 0 or avg <= 0 or max_size <= 0:  # 35-36 MISSING
        raise typer.BadParameter("Chunk sizes must be > 0")
    if not (min_size <= avg <= max_size):             # 37-38 MISSING
        raise typer.BadParameter("Require min <= avg <= max")
    return ChunkerConfig(...)
```

**Functionality**: Validates chunk size constraints before creating config
**What it covers**:
- Negative/zero chunk size rejection (line 35-36)
- Ordering constraint validation: min ≤ avg ≤ max (line 37-38)

**Testing Difficulty**: **EASY**
**Mocking Needed**: None (pure validation logic)
**Tests to add**:
- Call encode/decode/prime/verify with `--avg -1` (negative avg)
- Call encode with `--min 1000 --avg 500` (avg < min)
- Call encode with `--max 5000 --avg 10000` (avg > max)

**Estimated coverage if tested**: +4 lines

---

### Gap 2: Lines 83-114 (encode command - error handling)
**Function**: `encode()` command
**Location**: lines 47-115

```python
# Line 72-82: encrypt flag without key
if encrypt and not encryption_key:
    raise typer.Exit(code=_print_error(...))

# Lines 83-114 MISSING:
effective_encryption_key = encryption_key or os.environ.get("HELIX_ENCRYPTION_KEY")  # 83
if encrypt and not effective_encryption_key:  # 84-94 (this whole block)
    raise typer.Exit(code=_print_error(...))

try:  # 95
    stats = encode_file(...)  # 96-107
    typer.echo("encoded ...")  # 108-112
except HelixError as exc:  # 113-114
    raise typer.Exit(code=_print_error(exc))
```

**Functionality**: 
- Encryption key handling (env var fallback, validation)
- Successful encoding output and error handling

**What it covers**:
- Environment variable fallback when --encryption-key not provided
- Error when encrypt=True but no key available (double-check after env var)
- Successful encode execution with various chunker/compression options
- HelixError exception handling during encode

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**: 
- Mock `os.environ.get("HELIX_ENCRYPTION_KEY")`
- Mock `encode_file()` to return stats
- Create minimal test genomes

**Tests to add**:
- Test `helix encode --encrypt` without --encryption-key and without env var (should fail)
- Test `helix encode --encrypt` with env var HELIX_ENCRYPTION_KEY set (should succeed)
- Test `helix encode --no-encrypt` with various chunkers (cdc_buzhash, fixed)
- Test `helix encode` with different compression (zstd, zlib, none)
- Test `helix encode` with --learn/--no-learn flags
- Test `helix encode` with --portable/--no-portable flags
- Test `helix encode` with --manifest-private
- Test encode when encode_file raises HelixError

**Estimated coverage if tested**: +32 lines

---

### Gap 3: Lines 129-138 (decode command - error handling)
**Function**: `decode()` command
**Location**: lines 117-139

```python
def decode(...):
    try:  # 129-138 MISSING:
        digest = decode_file(...)  # 130-135
        typer.echo(f"decoded sha256={digest}")  # 136
    except HelixError as exc:  # 137-138
        raise typer.Exit(code=_print_error(exc))
```

**Functionality**:
- File decoding with optional encryption key
- Success output format
- Error handling

**What it covers**:
- Env var fallback for HELIX_ENCRYPTION_KEY
- Successful decode with output
- HelixError exception handling

**Testing Difficulty**: **EASY** (but requires encode first)
**Mocking Needed**:
- Mock `decode_file()` return value
- Or use real tiny seed from encode

**Tests to add**:
- Test decode with encrypted seed and correct key
- Test decode with encrypted seed and env var key
- Test decode with missing chunks (should catch HelixError)
- Test decode with unencrypted seed

**Estimated coverage if tested**: +10 lines

---

### Gap 4: Lines 167-197 (verify command - output formatting)
**Function**: `verify()` command  
**Location**: lines 141-198

```python
def verify(...):
    try:  # 167-176
        report = verify_seed(...)  # 168-175
    except HelixError as exc:  # 176-177
        raise typer.Exit(code=_print_error(exc))

    if report.ok:  # 179-185 MISSING:
        typer.echo(f"verify ok mode={'strict' if strict else 'quick'} ...")
        raise typer.Exit(code=0)

    typer.echo(f"verify failed: {report.reason}", err=True)  # 187-197 MISSING:
    if report.missing_count:
        typer.echo(f"missing_count={report.missing_count}", err=True)
        for h in report.missing_hashes:
            typer.echo(f"missing_chunk={h}", err=True)
    if report.expected_sha256 or report.actual_sha256:
        typer.echo(f"expected_sha256=... actual_sha256=...", err=True)
    raise typer.Exit(code=1)
```

**Functionality**:
- Verify output formatting for both success and failure
- Handling missing chunks display
- Strict vs quick mode output differentiation

**What it covers**:
- Success verify output (ok=True, quiet mode)
- Failed verify with reason text
- Missing chunks enumeration
- SHA256 mismatch reporting
- Exit codes (0 vs 1)
- --strict vs --no-strict formatting

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**:
- Mock `verify_seed()` to return success/failure reports

**Tests to add**:
- Test verify --strict with valid seed → should show "strict" in output
- Test verify --no-strict with valid seed → should show "quick" in output
- Test verify with missing chunks → should enumerate missing_chunk entries
- Test verify with SHA256 mismatch → should show expected/actual
- Test verify exit code = 0 on success
- Test verify exit code = 1 on failure
- Test verify --require-signature with unsigned seed
- Test verify --require-signature with valid signature

**Estimated coverage if tested**: +31 lines

---

### Gap 5: Lines 210-224 (prime command - error handling)
**Function**: `prime()` command
**Location**: lines 200-225

```python
def prime(...):
    try:  # 210-224 MISSING:
        stats = prime_genome(...)  # 211-216
        typer.echo(f"prime files={stats['files']} ...")  # 217-222
    except HelixError as exc:  # 223-224
        raise typer.Exit(code=_print_error(exc))
```

**Functionality**:
- Prime genome from directory/glob
- Success stats output
- Error handling

**What it covers**:
- Chunker config validation (via _cfg call)
- prime_genome execution
- Output formatting with dedup ratio
- Error handling

**Testing Difficulty**: **EASY**
**Mocking Needed**:
- Mock `prime_genome()` to return stats dict
- Or create test corpus directory

**Tests to add**:
- Test prime with directory glob pattern
- Test prime with dedup_ratio output formatting
- Test prime with invalid chunker config (leverages _cfg)
- Test prime when prime_genome raises HelixError

**Estimated coverage if tested**: +15 lines

---

### Gap 6: Lines 284-286 (publish OSError handling)
**Function**: `publish()` command
**Location**: lines 275-313

```python
def publish(...):
    try:  # 284-286 MISSING:
        with seed.open("rb") as f:
            if not is_encrypted_seed_data(f.read(4)):
                typer.echo("warning: publishing unencrypted seed...", err=True)
    except OSError:  # MISSING: pass handling
        pass
    try:
        cid = publish_seed(seed, pin=pin)
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))
```

**Functionality**:
- Pre-publish seed format check (unencrypted warning)
- Graceful degradation when seed file not readable

**What it covers**:
- OSError exception catching (file doesn't exist, unreadable)
- Early warning emission for unencrypted seeds
- Continues to publish_seed even if warning check fails

**Testing Difficulty**: **EASY**
**Mocking Needed**: None, but seed file needed or monkeypatch open()

**Tests to add**:
- Test publish with missing seed file (OSError)
- Test publish with unreadable seed (permission denied)
- Already covered: publish with encrypted seed (no warning)
- Already covered: publish with unencrypted seed (shows warning)

**Estimated coverage if tested**: +3 lines

---

### Gap 7: Lines 289-290 (publish command error handling)
**Function**: `publish()` command
**Location**: lines 287-313

```python
try:  # 289-290 MISSING:
    cid = publish_seed(seed, pin=pin)
except (HelixError, ExternalToolError) as exc:  # MISSING
    raise typer.Exit(code=_print_error(exc))
```

**Functionality**:
- Publish execution with pin option
- Error handling for IPFS failures

**What it covers**:
- publish_seed call with correct pin parameter
- HelixError exception handling
- ExternalToolError exception handling

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**:
- Mock `publish_seed()` return or raise exceptions

**Tests to add**:
- Test publish --pin (pin=True)
- Test publish --no-pin (pin=False)
- Test publish when publish_seed raises HelixError
- Test publish when publish_seed raises ExternalToolError

**Estimated coverage if tested**: +2 lines

---

### Gap 8: Lines 304-305 (remote_pin_cid error handling)
**Function**: `publish()` command with remote-pin
**Location**: lines 292-313

```python
if remote_pin:
    try:  # 304-305 MISSING:
        report = remote_pin_cid(...)
    except (HelixError, ExternalToolError) as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"remote_pin provider={report.provider} ...")
```

**Functionality**:
- Remote pinning with PSA provider
- Error handling for remote pin failures
- Remote pin output formatting

**What it covers**:
- remote_pin_cid function call with all parameters
- Exception handling
- Report formatting with optional request_id

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**: Mock `remote_pin_cid()` to return report or raise

**Tests to add**:
- Test publish --remote-pin with valid endpoint/token
- Test publish --remote-pin with custom timeout/retries
- Test publish --remote-pin with custom name
- Test when remote_pin_cid raises ExternalToolError
- Already covered: publish can trigger remote_pin (test_remote_pinning.py)

**Estimated coverage if tested**: +2 lines

---

### Gap 9: Lines 338-342 (fetch command - error handling)
**Function**: `fetch()` command
**Location**: lines 315-343

```python
def fetch(...):
    try:  # 338-342 MISSING:
        fetch_seed(cid, out, retries=retries, backoff_ms=backoff_ms, gateway=gateway)
    except (HelixError, ExternalToolError) as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"fetched {cid} -> {out}")
```

**Functionality**:
- Fetch seed from IPFS with retry/gateway params
- Success output
- Error handling

**What it covers**:
- fetch_seed call with all parameters
- HelixError and ExternalToolError handling
- Success message with paths

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `fetch_seed()`

**Tests to add**:
- Test fetch with custom retries
- Test fetch with custom backoff-ms
- Test fetch with gateway URL
- Test fetch when fetch_seed raises HelixError
- Test fetch when fetch_seed raises ExternalToolError

**Estimated coverage if tested**: +5 lines

---

### Gap 10: Lines 350-351 (pin-health command error handling)
**Function**: `pin_health()` command
**Location**: lines 345-360

```python
def pin_health(cid: str):
    try:  # 349-351 MISSING:
        report = pin_health_status(cid)
    except (HelixError, ExternalToolError) as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))

    typer.echo(f"pin_health cid={report['cid']} pinned={report['pinned']} ...")
    if report["reason"]:
        typer.echo(f"reason={report['reason']}", err=not bool(report["ok"]))
    raise typer.Exit(code=0 if report["ok"] else 1)
```

**Functionality**:
- Check IPFS pin status and block availability
- Conditional reason output
- Exit code based on ok status

**What it covers**:
- pin_health_status call
- Error handling
- Reason output with err= parameter
- Exit code logic

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `pin_health_status()`

**Tests to add**:
- Test pin-health with pinned=True
- Test pin-health with pinned=False
- Test pin-health with reason text
- Test pin-health exit code when ok=True
- Test pin-health exit code when ok=False
- Already partially covered: test_ipfs_reliability.py

**Estimated coverage if tested**: +2 lines

---

### Gap 11: Line 419 (pin remote-add success message)
**Function**: `pin_remote_add()` command
**Location**: lines 362-424

```python
def pin_remote_add(...):
    try:
        report = remote_pin_cid(...)
    except (HelixError, ExternalToolError) as exc:
        raise typer.Exit(code=_print_error(exc))

    typer.echo(  # 419-423 MISSING:
        "remote_pin "
        f"provider={report.provider} cid={report.cid} status={report.status} "
        f"request_id={report.request_id or 'none'}"
    )
```

**Functionality**:
- Remote add output formatting
- Handling optional request_id (None → 'none')

**What it covers**:
- Output formatting with conditional request_id display

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `remote_pin_cid()`

**Tests to add**:
- Test pin remote-add output format
- Test pin remote-add with request_id present
- Test pin remote-add with request_id=None
- Already covered: test_remote_pinning.py::test_pin_remote_add_cli_reports_error_code

**Estimated coverage if tested**: +5 lines

---

### Gap 12: Lines 433-434 (doctor command error handling)
**Function**: `doctor()` command
**Location**: lines 426-445

```python
def doctor(...):
    try:  # 432-434 MISSING:
        report = run_doctor(genome)
    except (HelixError, ExternalToolError) as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))

    for check in report.checks:
        typer.echo(f"[{check.status}] {check.check}: {check.detail}")
        if check.next_action and check.status in {"warn", "fail"}:
            typer.echo(f"next_action: {check.next_action}")
```

**Functionality**:
- Doctor diagnostics execution
- Error handling

**What it covers**:
- run_doctor call with genome path
- Exception handling
- Remaining lines (436-444) handle output

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `run_doctor()`

**Tests to add**:
- Test doctor when run_doctor raises HelixError
- Test doctor when run_doctor raises ExternalToolError
- Already covered: test_doctor.py (success/warn/fail cases)

**Estimated coverage if tested**: +3 lines

---

### Gap 13: Lines 501-517 (sign command - key handling and error)
**Function**: `sign()` command
**Location**: lines 489-518

```python
def sign(...):
    key = os.environ.get(key_env)  # 501
    if not key:  # 502-512 MISSING:
        raise typer.Exit(
            code=_print_error(
                HelixError(
                    f"Signing key env var is not set: {key_env}. ...",
                    code="HELIX_E_SIGNING_KEY_MISSING",
                    next_action=f"Export `{key_env}` with your HMAC signing key...",
                )
            )
        )
    try:  # 513-517 MISSING:
        sign_seed_file(seed, out, signature_key=key, signature_key_id=key_id)
    except HelixError as exc:
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"signed {seed} -> {out} key_id={key_id}")
```

**Functionality**:
- HMAC signature generation
- Signing key validation from environment
- Error handling

**What it covers**:
- Environment variable reading
- Missing key error with code + next_action
- sign_seed_file execution with key_id parameter
- Success output format
- HelixError handling

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock environment, monkeypatch os.environ

**Tests to add**:
- Test sign without HELIX_SIGNING_KEY env var (should fail)
- Test sign with --key-env custom name
- Test sign with --key-id custom ID
- Test sign when sign_seed_file raises HelixError
- Test sign success output format

**Estimated coverage if tested**: +17 lines

---

### Gap 14: Lines 527-531 (export-genes error handling)
**Function**: `export_genes_cmd()` command
**Location**: lines 520-534

```python
def export_genes_cmd(...):
    try:  # 527-531 MISSING:
        stats = export_genes(seed, genome, out)
    except HelixError as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"exported total={stats['total']} exported={stats['exported']} missing={stats['missing']}")
```

**Functionality**:
- Export genes pack from seed
- Error handling
- Success output

**What it covers**:
- export_genes execution
- HelixError exception handling
- Output with stats dict

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**: Mock `export_genes()`

**Tests to add**:
- Test export-genes output format
- Test export-genes with missing chunks
- Test export-genes when export_genes raises HelixError
- Already partially covered: test_genes_pack.py

**Estimated coverage if tested**: +5 lines

---

### Gap 15: Lines 542-546 (import-genes error handling)
**Function**: `import_genes_cmd()` command
**Location**: lines 536-547

```python
def import_genes_cmd(...):
    try:  # 542-546 MISSING:
        stats = import_genes(pack, genome)
    except HelixError as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"imported inserted={stats['inserted']} skipped={stats['skipped']}")
```

**Functionality**:
- Import genes pack into genome
- Error handling
- Success output

**What it covers**:
- import_genes execution
- HelixError exception handling
- Output with stats dict

**Testing Difficulty**: **MEDIUM**
**Mocking Needed**: Mock `import_genes()`

**Tests to add**:
- Test import-genes output format
- Test import-genes duplicate handling
- Test import-genes when import_genes raises HelixError
- Already partially covered: test_genes_pack.py

**Estimated coverage if tested**: +5 lines

---

### Gap 16: Lines 555-559 (genome snapshot error handling)
**Function**: `genome_snapshot()` command
**Location**: lines 549-560

```python
@genome_app.command("snapshot")
def genome_snapshot(...):
    try:  # 555-559 MISSING:
        stats = snapshot_genome(genome, out)
    except HelixError as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"snapshot chunks={stats['chunks']} bytes={stats['bytes']} out={out}")
```

**Functionality**:
- Snapshot all genome chunks to portable file
- Error handling
- Success output

**What it covers**:
- snapshot_genome execution
- HelixError exception handling
- Output with stats and path

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `snapshot_genome()`

**Tests to add**:
- Test genome snapshot output format
- Test genome snapshot when snapshot_genome raises HelixError
- Already partially covered: test_genome_snapshot.py

**Estimated coverage if tested**: +5 lines

---

### Gap 17: Lines 573-577 (genome restore error handling)
**Function**: `genome_restore()` command
**Location**: lines 562-581

```python
@genome_app.command("restore")
def genome_restore(...):
    try:  # 573-577 MISSING:
        stats = restore_genome(snapshot, genome, replace=replace)
    except HelixError as exc:  # MISSING
        raise typer.Exit(code=_print_error(exc))
    typer.echo(f"restored entries={stats['entries']} inserted={stats['inserted']} skipped={stats['skipped']}")
```

**Functionality**:
- Restore genome chunks from snapshot file
- Error handling with replace option
- Success output

**What it covers**:
- restore_genome execution with replace flag
- HelixError exception handling
- Output with three stat fields

**Testing Difficulty**: **EASY**
**Mocking Needed**: Mock `restore_genome()`

**Tests to add**:
- Test genome restore output format
- Test genome restore --replace vs --no-replace
- Test genome restore when restore_genome raises HelixError
- Already partially covered: test_genome_snapshot.py

**Estimated coverage if tested**: +5 lines

---

### Gap 18: Lines 590-591 (_print_error fallback)
**Function**: `_print_error()` helper
**Location**: lines 583-592

```python
def _print_error(exc: Exception) -> int:
    if isinstance(exc, HelixError):  # 584-588
        info = exc.as_info()
        typer.echo(f"error[{info.code}]: {info.message}", err=True)
        if info.next_action:
            typer.echo(f"next_action: {info.next_action}", err=True)
        return 1
    typer.echo(f"error[HELIX_E_UNKNOWN]: {exc}", err=True)  # 590-591 MISSING
    return 1
```

**Functionality**:
- Generic exception handling fallback
- Unknown error formatting

**What it covers**:
- Non-HelixError exception output
- Generic error code and message

**Testing Difficulty**: **EASY**
**Mocking Needed**: Raise non-HelixError exceptions

**Tests to add**:
- Test any CLI command with a non-HelixError exception
- Or mock encode_file to raise ValueError
- Test output includes "HELIX_E_UNKNOWN"

**Estimated coverage if tested**: +2 lines

---

## Summary Table

| Gap | Lines | Function | Difficulty | Est. Lines | Key Test Areas |
|-----|-------|----------|------------|-----------|-----------------|
| 1 | 35-39 | _cfg | Easy | 4 | Parameter validation |
| 2 | 83-114 | encode | Medium | 32 | Encryption, compression, output |
| 3 | 129-138 | decode | Easy | 10 | Decryption, output, error handling |
| 4 | 167-197 | verify | Medium | 31 | Strict/quick, missing chunks, output |
| 5 | 210-224 | prime | Easy | 15 | Prime output, error handling |
| 6 | 284-286 | publish | Easy | 3 | OSError, warning check |
| 7 | 289-290 | publish | Medium | 2 | Error handling |
| 8 | 304-305 | publish | Medium | 2 | Remote pin error handling |
| 9 | 338-342 | fetch | Easy | 5 | Fetch params, error handling |
| 10 | 350-351 | pin-health | Easy | 2 | Status output, error handling |
| 11 | 419 | pin_remote_add | Easy | 5 | Output formatting |
| 12 | 433-434 | doctor | Easy | 3 | Error handling |
| 13 | 501-517 | sign | Easy | 17 | Key handling, output |
| 14 | 527-531 | export_genes | Medium | 5 | Stats output, error handling |
| 15 | 542-546 | import_genes | Medium | 5 | Stats output, error handling |
| 16 | 555-559 | genome snapshot | Easy | 5 | Output format |
| 17 | 573-577 | genome restore | Easy | 5 | Replace option, output |
| 18 | 590-591 | _print_error | Easy | 2 | Non-HelixError fallback |

**Total Potential Coverage Gain**: ~152 lines (estimated when all gaps tested)

---

## Recommended Testing Order (by Impact & Complexity)

### Priority 1: High Impact, Easy Implementation
1. **Gap 2 (encode)**: 32 lines - core functionality
2. **Gap 4 (verify)**: 31 lines - core functionality with multiple paths
3. **Gap 5 (prime)**: 15 lines - common operation
4. **Gap 13 (sign)**: 17 lines - important feature

### Priority 2: Medium Impact, Easy Implementation
5. **Gap 3 (decode)**: 10 lines - core roundtrip
6. **Gap 1 (_cfg validation)**: 4 lines - guards all chunking commands
7. **Gap 9 (fetch)**: 5 lines - IPFS operations
8. **Gap 16-17 (genome ops)**: 10 lines combined

### Priority 3: Lower Priority/IPFS-dependent
9. **Gap 6-8 (publish variants)**: 7 lines - IPFS heavy
10. **Gap 10-11 (pin operations)**: 7 lines - IPFS heavy
11. **Gap 14-15 (genes/import)**: 10 lines - specialized features
12. **Gap 12 (doctor)**: 3 lines - mostly mocked already
13. **Gap 18 (_print_error)**: 2 lines - fallback path

---

## Test Infrastructure Recommendations

### Suggested Fixtures
- Minimal encoded seed (10KB for fast tests)
- Various genome states (empty, populated)
- Mock response objects for IPFS operations

### Mocking Strategy
- Mock `encode_file`, `decode_file`, `verify_seed` in CLI tests
- Use real codec tests to verify those functions (already have coverage)
- Focus CLI tests on command parsing, error handling, output formatting

### Test File Organization
- Create `tests/test_cli_encode.py` for encode/chunker validation
- Create `tests/test_cli_verify.py` for verify/signature tests
- Create `tests/test_cli_crypto.py` for encrypt/sign operations
- Create `tests/test_cli_ipfs.py` for publish/fetch/pin operations
- Create `tests/test_cli_genome.py` for genome snapshot/restore
- Create `tests/test_cli_genes.py` for export/import genes

---

## Notes

- Lines 72-82, 95-107, 113 in encode are already covered (not in missing list)
- Most _print_error calls are covered (only lines 590-591 missing)
- Successful paths in several commands are covered; missing paths are error handling
- IPFS tests can skip when ipfs CLI unavailable (use pytest.skip)
- Encryption key handling is split between CLI prompt and env var fallback
