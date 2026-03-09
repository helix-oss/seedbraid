# Changelog

All notable changes to Seedbraid are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow [PEP 440](https://peps.python.org/pep-0440/).

## [Unreleased]

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

[Unreleased]: https://github.com/aimsise/seedbraid/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/aimsise/seedbraid/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/aimsise/seedbraid/compare/v1.0.0b2...v1.1.0
[1.0.0b2]: https://github.com/aimsise/seedbraid/compare/v1.0.0b1...v1.0.0b2
[1.0.0b1]: https://github.com/aimsise/seedbraid/compare/v1.0.0...v1.0.0b1
[1.0.0]: https://github.com/aimsise/seedbraid/releases/tag/v1.0.0
