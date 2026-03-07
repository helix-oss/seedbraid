# Helix

Reference-based file reconstruction with CDC chunking, HLX1 binary seed
format, and IPFS transport.

## Overview

Helix provides a seed-first architecture for efficient file distribution:

- **Lossless encode/decode** with SHA-256 verification
- **Content-Defined Chunking** (CDC): `fixed`, `cdc_buzhash`, `cdc_rabin`
- **Genome storage** (SQLite) for deduplicated chunk reuse
- **HLX1 binary seed format** with TLV sections
- **IPFS integration** for publish/fetch transport
- **Optional encryption and signing** for secure distribution

## Quick Start

```bash
# Install
uv sync --no-editable --extra dev

# Encode a file
uv run helix encode input.bin --genome ./genome --out seed.hlx

# Decode (reconstruct)
uv run helix decode seed.hlx --genome ./genome --out recovered.bin

# Verify integrity
uv run helix verify seed.hlx --genome ./genome --strict
```

## Architecture

CDC anchors chunk boundaries on rolling hash fingerprints for
byte-shift-resilient dedup. SQLite genome stores chunks for portability
over peak throughput. HLX1 binary TLV format enables forward-compatible
section growth.

See [Design](DESIGN.md) for detailed architecture documentation
and [Format Spec](FORMAT.md) for the HLX1 binary specification.

## API Reference

The [API Reference](api/index.md) provides auto-generated documentation
for all public modules, built from source code docstrings.
