# Changelog

All notable changes to Seedbraid are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow [PEP 440](https://peps.python.org/pep-0440/).

## [Unreleased]

## [2.0.5] - 2026-04-04

### Fixed
- Remediate security audit findings across 8 modules (T-035): chunk hash verification on decode, size limits on IPFS fetches, scrypt parameter validation, MIME header injection prevention, CID match verification in PSA responses (#46)
- Allow `git reset --hard origin/<branch>` in pre-bash safety hook (#47)
- Use sed-strip approach for origin reset exception in safety hook (#48)

## [2.0.4] - 2026-04-04

### Fixed
- Remove `model: sonnet` override from `/release` skill to avoid spurious rate limit errors on Opus → Sonnet inline model switch (#44)

## [2.0.3] - 2026-04-04

### Added
- `/scout` skill: orchestrator chaining `/investigate` (sonnet) + `/plan2doc` (opus) for cost-optimized research+planning (#42)
- `/impl` skill: plan execution with lint/test loop, `/simplify` review, and post-simplify verification (#42)
- `/ship` skill: combined commit + PR creation + optional squash-merge workflow (#41)

### Changed
- `plan2doc` skill: restored to planning-only focus, added error handling and existing research context (#42)
- `planner` agent: simplified to caller-delegated instructions, added Edit and Bash(git:*) tools (#42)

### Fixed
- CI: replaced unreliable `ipfs/download-ipfs-distribution-action` with direct GitHub Releases download, bumped kubo v0.32.1 → v0.34.1 (#41)

### Tests
- CDC shift-resilient chunking: added Rabin prefix invariance and BuzHash suffix reuse tests (T-028b/c) (#40)

## [2.0.2] - 2026-04-02

### Added
- Claude Code harness engineering Phase 1 + Phase 2: skills, custom agents, and release workflow (#38)

## [2.0.1] - 2026-03-26

### Documentation
- README: add remote pinning setup and verification guide (#36)
- README: add data recovery scenarios and protection strategies (#35)

## [2.0.0] - 2026-03-25

### Changed
- Version bumped to 2.0.0: IPFS distributed chunk storage as major architectural expansion
- All IPFS operations migrated from subprocess CLI calls to kubo HTTP RPC API (`/api/v0/`) via stdlib `urllib.request`
- `SB_KUBO_API` environment variable for configurable kubo API endpoint (default `http://127.0.0.1:5001/api/v0`)
- CI: kubo daemon startup with health check polling for IPFS E2E tests
- IPFS tests now skip based on kubo daemon reachability instead of `ipfs` CLI presence

### Added
- `ipfs_http.py`: kubo HTTP RPC client module (thin wrapper over urllib)
- `SB_E_KUBO_API_ERROR` and `SB_E_KUBO_API_UNREACHABLE` error codes

### Documentation
- CLAUDE.md: updated module list (16 modules), CLI commands (17 commands), crypto extra, ERROR_CODES.md ref
- README.md: IPFS Setup section rewritten for kubo daemon prerequisites; added `SB_KUBO_API` documentation
- CONTRIBUTING.md: added kubo daemon as prerequisite for IPFS E2E tests
- API reference: added docs for ipfs_chunks, chunk_manifest, hybrid_storage, cid modules
- mkdocs.yml: nav updated with 4 new API reference entries
- DESIGN.md: Architecture module list updated with 4 new modules; kubo HTTP API migration documented
- THREAT_MODEL.md: added kubo HTTP API transport security considerations
- ERROR_CODES.md: added kubo API error codes
- index.md: added IPFS distributed chunks to feature overview
- PERFORMANCE.md: updated deferred benchmark integration note

### Removed
- `SB_E_IPFS_CHUNK_UNAVAILABLE` error code (never implemented; chunk fetch failures use `SB_E_IPFS_CHUNK_GET`)
- All `subprocess` calls for IPFS operations in source and test files

## [1.2.0] - 2026-03-22

### Added
- IPFS distributed chunk storage (SBD-ECO-006):
  - New CLI command `publish-chunks` for publishing CDC chunks to IPFS as raw blocks
  - New CLI command `fetch-decode` for reconstructing files from IPFS-hosted chunks
  - `--genome ipfs://` URI support for hybrid local+IPFS decode
  - Chunk DAG pinning via IPFS MFS with local/remote pin options
  - `HybridGenomeStorage` combining local SQLite with IPFS fallback and caching
  - `IPFSChunkStorage` implementing `GenomeStorage` Protocol over IPFS subprocess calls
  - CIDv1 (raw codec, base32-lower) deterministic computation from SHA-256 digest
  - Chunk manifest sidecar format (`.sbd.chunks.json`)
  - Parallel publish via `ThreadPoolExecutor` (default 16 workers)
  - Batched parallel fetch (default `batch_size=100`) for streaming-first memory model

### Added (Error Codes)
- `SB_E_IPFS_CHUNK_PUT` for chunk publish failures
- `SB_E_IPFS_CHUNK_GET` for chunk fetch failures
- `SB_E_CHUNK_MANIFEST_FORMAT` for invalid manifest sidecar
- `SB_E_IPFS_MFS` for MFS operation failures during DAG construction

### Documentation
- DESIGN.md updated with full SBD-ECO-006 implementation details
- README updated with publish-chunks, fetch-decode, and ipfs:// genome examples
- ERROR_CODES.md updated with IPFS chunk error codes
- PERFORMANCE.md updated with IPFS chunk fetch baseline metrics

## [1.1.3] - 2026-03-10

### Documentation
- README を「価値提案 → Quick Start → 詳細」の順に再構成し、ユーザーオンボーディングを改善 (#31)
- Quick Start の encode コマンドを `--portable` のみに簡素化 (#31)
- CLI Reference を Core Commands / Advanced Commands に分割 (#31)
- ユーザー向けセクションと開発者セクションを水平線で分離 (#31)
- 全 CLI コマンド例を bare `seedbraid` に統一 (#31)

## [1.1.2] - 2026-03-10

### Added
- CLI に `--version` / `-V` フラグを追加 (#29)

### Documentation
- README の Installation セクションを pip/pipx/uvx インストール例に更新 (#29)
- README の Quick Start を Development Setup にリネーム (#29)

## [1.1.1] - 2026-03-10

### Maintenance
- PyPI パッケージメタデータ追加: license, authors, classifiers, project URLs (#27)

## [1.1.0] - 2026-03-10

### Changed
- **BREAKING**: プロジェクト名を helix から seedbraid に完全リネーム (#21)
  - パッケージ: `helix` → `seedbraid`、CLI: `helix` → `seedbraid`
  - バイナリマジック: HLX1→SBD1, HLE1→SBE1, HGS1→SGS1
  - HKDF info: `helix-hle1-v3-aead-key` → `seedbraid-sbe1-v3-aead-key`
  - ファイル拡張子: `.hlx`→`.sbd`, `.hgs`→`.sgs`
  - エラーコード: `HELIX_E_*` → `SB_E_*`、環境変数: `HELIX_*` → `SB_*`
  - OCI メディアタイプ: `vnd.helix.*` → `vnd.seedbraid.*`
- GitHub リポジトリを `aimsise/seedbraid` に移行

### Fixed
- OCI メディアタイプサフィックスを `+hlx` → `+sbd` に修正 (#24)

### Documentation
- T-012 ヘルパー関数に Google-style docstring を追加 (#23)

### Maintenance
- GitHub 参照を `aimsise/seedbraid` に更新 (#22)
- `.gitignore` のパターンを `.sbd` 拡張子に更新 (#25)

## [1.0.0b2] - 2026-03-08

### Documentation
- THREAT_MODEL.md の HLE1 v3 AEAD KDF セクションを拡充 (#17)

### Maintenance
- 内部開発ドキュメントを `.docs/` に整理し、`docs/` を公開ドキュメントのみに統一 (#16)

### CI
- `actions/checkout` v4 → v6 (#4)
- `actions/setup-python` v5 → v6 (#3)
- `astral-sh/setup-uv` v5 → v7 (#5)
- `actions/upload-artifact` v4 → v7 (#1)
- `actions/download-artifact` v4 → v8 (#2)

## [1.0.0b1] - 2026-03-08

### Added
- Tag-based release automation with PyPI Trusted Publishing (OIDC) (T-014)
- pytest-cov integration and CI coverage gate at 80% (T-002)
- Dependabot config for pip and github-actions dependencies (T-011)
- CODEOWNERS for automatic review assignment (T-016)
- Community standards: Issue/PR templates and Code of Conduct (T-015)
- Claude Code subagent definitions and custom commands
- AEAD encryption (AES-256-GCM) with HLE1 v3 header format (T-010)
- MkDocs API reference documentation with mkdocstrings (T-013)
- Branch protection configuration (T-018)
- GitHub Sponsors FUNDING.yml (T-019)

### Changed
- HLE1 encryption header uplifted to v2: scrypt n=32768 for stronger KDF (T-005)
- GenomeStorage now supports context manager protocol (T-003)
- ruff line-length set to 79 across all source files (PEP 8 compliance)
- CLI plan/review commands renamed to avoid built-in name conflicts
- All error raises in container/codec now include next_action guidance (T-006)
- Long functions decomposed into private helpers for maintainability (T-012)

### Fixed
- Eliminated duplicate scrypt call in decrypt_seed_bytes (T-004)
- Consistent blank line after module docstrings (T-007)
- `__init__.py` is now single source of truth for version string (T-001)

### Security
- scrypt KDF hardened to resist GPU/ASIC attacks: N=32768, r=8, p=1 in HLE1 v2 (T-005)
- Crypto migration to AEAD (AES-256-GCM) with HKDF-SHA256 key derivation in HLE1 v3 (T-010)

## [1.0.0] - 2026-02-17

Initial OSS public release.

### Added
- CDC chunking with rolling hash for byte-shift-resilient deduplication
- HLX1 binary TLV seed format with forward-compatible section growth
- SQLite genome storage for portable chunk management
- Optional seed encryption (HLE1 v1, scrypt-based)
- Optional seed signature verification (Ed25519)
- Section SHA-256 integrity checks for HLX1
- Genome snapshot and restore commands
- Strict verify mode for full reconstruction checks
- IPFS transport with retry logic and pin health checks
- Private-manifest mode and publish warnings
- Doctor command with actionable error codes
- DVC workflow bridge (HLX-ECO-003)
- OCI/ORAS bridge (HLX-ECO-004)
- ML hooks integration (HLX-ECO-005)
- CI benchmark gates for dedup ratio and throughput
- Compatibility fixture regression coverage

[Unreleased]: https://github.com/aimsise/seedbraid/compare/v2.0.5...HEAD
[2.0.5]: https://github.com/aimsise/seedbraid/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/aimsise/seedbraid/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/aimsise/seedbraid/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/aimsise/seedbraid/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/aimsise/seedbraid/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/aimsise/seedbraid/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/aimsise/seedbraid/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/aimsise/seedbraid/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/aimsise/seedbraid/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/aimsise/seedbraid/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/aimsise/seedbraid/compare/v1.0.0b2...v1.1.0
[1.0.0b2]: https://github.com/aimsise/seedbraid/compare/v1.0.0b1...v1.0.0b2
[1.0.0b1]: https://github.com/aimsise/seedbraid/compare/v1.0.0...v1.0.0b1
[1.0.0]: https://github.com/aimsise/seedbraid/releases/tag/v1.0.0
