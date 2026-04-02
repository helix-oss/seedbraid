# Seedbraid Testing Conventions (Reference)

Source: `.claude/rules/testing.md` and existing test patterns

## Test Structure

```
tests/
├── test_chunking.py        # CDC chunking tests
├── test_codec.py           # Encode/decode tests
├── test_container.py       # Binary container tests
├── test_storage.py         # Genome storage tests
├── test_ipfs.py            # IPFS integration (auto-skip)
├── test_pinning.py         # Pinning service tests
├── test_cid.py             # CID validation tests
├── test_cli.py             # CLI integration tests
├── test_perf.py            # Performance regression tests
├── fixtures/
│   ├── compat/             # Committed version-gated fixtures
│   └── ...                 # Temporary test data
```

## IPFS Test Skipping Pattern

```python
import pytest
import shutil

IPFS_AVAILABLE = shutil.which("ipfs") is not None

@pytest.mark.skipif(not IPFS_AVAILABLE, reason="ipfs CLI not available")
def test_ipfs_publish():
    ...
```

## Fixture Conventions

- Use `tmp_path` (pytest built-in) for temporary files.
- Committed fixtures must be small and deterministic.
- Large test data should be generated programmatically in fixtures.
- Compatibility fixtures are regenerated only when binary format changes.

## Security Test Notes

When modifying tests for encryption, signatures, or verify logic:
- Document the security implication in PR description.
- Ensure test does not leak keys or sensitive data to fixtures.
- Test both valid and invalid/corrupted inputs.
