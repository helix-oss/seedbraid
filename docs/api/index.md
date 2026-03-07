# API Reference

Auto-generated reference documentation for all public Helix modules.
Built from Google-style docstrings using
[mkdocstrings](https://mkdocstrings.github.io/).

## Module Overview

### Core

| Module | Description |
|--------|-------------|
| [`helix.codec`](codec.md) | Encode, decode, verify, and genome management operations |
| [`helix.container`](container.md) | HLX1 binary seed container serialization and parsing |
| [`helix.chunking`](chunking.md) | Content-Defined Chunking (CDC) and fixed chunking algorithms |
| [`helix.storage`](storage.md) | Genome storage protocol and SQLite implementation |

### CLI

| Module | Description |
|--------|-------------|
| [`helix.cli`](cli.md) | Typer-based command-line interface |

### Transport

| Module | Description |
|--------|-------------|
| [`helix.ipfs`](ipfs.md) | IPFS publish, fetch, and pin operations |
| [`helix.pinning`](pinning.md) | Remote pinning service integration |
| [`helix.oci`](oci.md) | OCI/ORAS artifact distribution |

### Integrations

| Module | Description |
|--------|-------------|
| [`helix.mlhooks`](mlhooks.md) | MLflow and Hugging Face integration hooks |
| [`helix.perf`](perf.md) | Performance benchmarking and gate evaluation |
| [`helix.diagnostics`](diagnostics.md) | Runtime diagnostics and doctor checks |

### Utilities

| Module | Description |
|--------|-------------|
| [`helix.errors`](errors.md) | Exception hierarchy and error codes |
