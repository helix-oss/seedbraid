# Seedbraid

Reference-based file reconstruction with CDC chunking, SBD1 binary seed
format, and IPFS transport.

## Overview

Seedbraid provides a seed-first architecture for efficient file distribution:

- **Lossless encode/decode** with SHA-256 verification
- **Content-Defined Chunking** (CDC): `fixed`, `cdc_buzhash`, `cdc_rabin`
- **Genome storage** (SQLite) for deduplicated chunk reuse
- **SBD1 binary seed format** with TLV sections
- **IPFS integration** for publish/fetch transport
- **Optional encryption and signing** for secure distribution

## Quick Start

```bash
# Install
uv sync --no-editable --extra dev

# Encode a file
uv run seedbraid encode input.bin --genome ./genome --out seed.sbd

# Decode (reconstruct)
uv run seedbraid decode seed.sbd --genome ./genome --out recovered.bin

# Verify integrity
uv run seedbraid verify seed.sbd --genome ./genome --strict
```

## Architecture

CDC anchors chunk boundaries on rolling hash fingerprints for
byte-shift-resilient dedup. SQLite genome stores chunks for portability
over peak throughput. SBD1 binary TLV format enables forward-compatible
section growth.

See [Design](DESIGN.md) for detailed architecture documentation
and [Format Spec](FORMAT.md) for the SBD1 binary specification.

## API Reference

The [API Reference](api/index.md) provides auto-generated documentation
for all public modules, built from source code docstrings.
