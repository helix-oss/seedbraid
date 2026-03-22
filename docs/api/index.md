# API Reference

Auto-generated reference documentation for all public Seedbraid modules.
Built from Google-style docstrings using
[mkdocstrings](https://mkdocstrings.github.io/).

## Module Overview

### Core

| Module | Description |
|--------|-------------|
| [`seedbraid.codec`](codec.md) | Encode, decode, verify, and genome management operations |
| [`seedbraid.container`](container.md) | SBD1 binary seed container serialization and parsing |
| [`seedbraid.chunking`](chunking.md) | Content-Defined Chunking (CDC) and fixed chunking algorithms |
| [`seedbraid.storage`](storage.md) | Genome storage protocol and SQLite implementation |
| [`seedbraid.hybrid_storage`](hybrid_storage.md) | Hybrid local+IPFS genome storage with caching |

### CLI

| Module | Description |
|--------|-------------|
| [`seedbraid.cli`](cli.md) | Typer-based command-line interface |

### Transport

| Module | Description |
|--------|-------------|
| [`seedbraid.ipfs`](ipfs.md) | IPFS publish, fetch, and pin operations |
| [`seedbraid.ipfs_chunks`](ipfs_chunks.md) | IPFS individual chunk publish/fetch operations |
| [`seedbraid.chunk_manifest`](chunk_manifest.md) | Chunk CID sidecar manifest management |
| [`seedbraid.cid`](cid.md) | CIDv1 deterministic computation from SHA-256 |
| [`seedbraid.pinning`](pinning.md) | Remote pinning service integration |
| [`seedbraid.oci`](oci.md) | OCI/ORAS artifact distribution |

### Integrations

| Module | Description |
|--------|-------------|
| [`seedbraid.mlhooks`](mlhooks.md) | MLflow and Hugging Face integration hooks |
| [`seedbraid.perf`](perf.md) | Performance benchmarking and gate evaluation |
| [`seedbraid.diagnostics`](diagnostics.md) | Runtime diagnostics and doctor checks |

### Utilities

| Module | Description |
|--------|-------------|
| [`seedbraid.errors`](errors.md) | Exception hierarchy and error codes |
