# T-016 CODEOWNERS Definition - 調査報告

**Date**: 2026-03-06  
**Status**: 完了  
**Prepared for**: T-016 実装フェーズ

## エグゼクティブサマリー

T-016は `.github/CODEOWNERS` ファイルの新規作成チケットです。現在、CODEOWNERS ファイルが存在しないため、GitHub の自動レビューリクエスト機能が機能していません。本調査では、プロジェクト構造、セキュリティクリティカルなパス、CI/DevOps ファイル、ドキュメント、テストの分類を行い、推奨される CODEOWNERS 設計案を提示します。

---

## 1. 現状分析

### 1.1 既存のCODEOWNERSファイル

```bash
$ find /Users/kytk/workspace/repos/helix -name "CODEOWNERS" 2>/dev/null
# 出力なし → CODEOWNERS ファイルが存在しない
```

**結論**: `.github/CODEOWNERS` は未作成です。

### 1.2 既存のコミュニティ標準設定（T-015で完了）

T-015 で実装済みの Community Standards:

| ファイル | 状態 | 目的 |
|---------|------|------|
| `CODE_OF_CONDUCT.md` | ✅ | Contributor Covenant v2.1 |
| `CONTRIBUTING.md` | ✅ | 開発ワークフロー・スタイル規約 |
| `.github/PULL_REQUEST_TEMPLATE.md` | ✅ | PR テンプレート |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | ✅ | バグ報告テンプレート |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | ✅ | 機能リクエストテンプレート |
| `SECURITY.md` | ✅ | セキュリティ報告ポリシー |

これらは CODEOWNERS と連携して、PR の自動レビューリクエストを実現できます。

### 1.3 リポジトリの基本情報

| 項目 | 値 |
|------|-----|
| 組織 | `helix-oss` |
| リポジトリ URL | `https://github.com/helix-oss/helix.git` |
| Git メール設定 | `helix-oss@users.noreply.github.com` |
| 主要コミッター | `Helix <helix-oss@users.noreply.github.com>` (34 commits) |
| リポジトリタイプ | オープンソース（OSS） |
| 現在のバージョン | `1.0.0a1` (alpha) |

---

## 2. プロジェクト構造とオーナーシップマッピング

### 2.1 ソースコード構造（`src/helix/`）

**モジュール一覧** (合計: 3,333 行):

| モジュール | LOC | 責務 | セキュリティ | 優先度 |
|-----------|-----|------|-------------|--------|
| `cli.py` | 591 | CLI コマンドインターフェース（encode, decode, verify, publish など） | 中 | 高 |
| `codec.py` | 550 | エンコード/デコード・検証ロジック（genome 操作含む） | 高 | 高 |
| `container.py` | 529 | HLX1/HLE1 バイナリシリアライゼーション・パース | **最高** | 最高 |
| `mlhooks.py` | 352 | ML/AI ワークフロー統合（DVC, OCI, ORAS ブリッジ） | 低 | 中 |
| `ipfs.py` | 277 | IPFS CLI ラッパー（publish/fetch/pin） | 高 | 高 |
| `pinning.py` | 231 | リモートピニングサービス（PSA 互換） | 高 | 中 |
| `diagnostics.py` | 183 | ヘルスチェック・診断（doctor コマンド） | 低 | 中 |
| `perf.py` | 173 | パフォーマンスゲート・ベンチマーク | 低 | 低 |
| `oci.py` | 144 | OCI/ORAS レジストリ統合 | 中 | 中 |
| `chunking.py` | 140 | CDC（content-defined chunking）実装 | 中 | 高 |
| `storage.py` | 85 | SQLite genome ストレージ | 高 | 高 |
| `errors.py` | 71 | エラーコード・エラーハンドリング | 中 | 中 |

**セキュリティクリティカルなモジュール** (レビュー必須):
- `container.py` → バイナリ形式パース、整合性検証、署名/暗号化
- `codec.py` → エンコード/デコード・genome 整合性
- `ipfs.py` → Web3 トランスポート、ダウンロード検証
- `storage.py` → genome データベース・チャンク管理
- `pinning.py` → リモートピニング・可用性管理

### 2.2 ドキュメント構造（`docs/`）

| ファイル | 目的 | 更新頻度 |
|---------|------|---------|
| `FORMAT.md` | HLX1/HLE1 バイナリ仕様 | 設計フェーズ時のみ |
| `DESIGN.md` | アーキテクチャ・意思決定 | 重要変更時 |
| `THREAT_MODEL.md` | セキュリティリスク・対策 | セキュリティ機能追加時 |
| `PERFORMANCE.md` | パフォーマンス目標・閾値 | ベンチマーク更新時 |
| `ERROR_CODES.md` | エラーコード仕様 | エラー追加時 |

**ドキュメント保守の責任**:
- 仕様変更（FORMAT.md, DESIGN.md） → 核心開発者
- セキュリティ更新 → セキュリティレビュアー

### 2.3 CI/DevOps 構造（`.github/`）

**Workflows**:

| ファイル | 目的 | トリガー |
|---------|------|---------|
| `.github/workflows/ci.yml` | Lint, Test, Compat, Benchmark | PR/push to main |
| `.github/workflows/publish-seed.yml` | リリース時シード発行 | Manual dispatch |

**CI 構成**:
- **Lint**: `ruff check .` (3.12 環境)
- **Test**: `pytest --cov-fail-under=80` (3.12 環境)
- **Compat**: `pytest tests/test_compat_fixtures.py`
- **Bench**: `scripts/bench_gate.py` (パフォーマンスゲート)

### 2.4 テスト構造（`tests/` 全 23 ファイル）

**セキュリティ関連テスト**:
- `test_container.py` → HLX1 パース
- `test_signature.py` → HMAC-SHA256 署名
- `test_encryption.py` → HLE1 暗号化
- `test_ipfs_*.py` → IPFS 検証

**その他テスト**:
- `test_cli_commands.py`, `test_roundtrip.py`, `test_perf.py` など

---

## 3. 推奨CODEOWNERS設計案

### 3.1 実装形式：プレースホルダー版（推奨）

**ファイル**: `.github/CODEOWNERS`

```
# Helix CODEOWNERS
# See GitHub documentation: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
#
# Code ownership rules are enforced for pull requests targeting the main branch.
# When a PR modifies files matching a pattern below, the specified owners are
# automatically requested for review.
#
# Guidelines:
# - Default: all changes require review from maintainers
# - Security-critical paths: require security reviewer
# - CI/DevOps: require DevOps team
# - Tests: require QA/test engineer

# Default: All files require maintainers review
* @helix-oss/maintainers

# Security-Critical Paths
# These modules handle cryptographic operations, binary format parsing,
# and data integrity verification. Any changes require security review.
src/helix/container.py       @helix-oss/security-reviewers
src/helix/codec.py           @helix-oss/security-reviewers
src/helix/ipfs.py            @helix-oss/security-reviewers
src/helix/storage.py         @helix-oss/security-reviewers
src/helix/pinning.py         @helix-oss/security-reviewers
src/helix/errors.py          @helix-oss/security-reviewers

# Specification & Design Documentation
# Format/design changes require architecture review and security sign-off
docs/FORMAT.md               @helix-oss/maintainers @helix-oss/security-reviewers
docs/THREAT_MODEL.md         @helix-oss/security-reviewers

# CI/DevOps
# Workflow and infrastructure changes require DevOps review
.github/                     @helix-oss/devops
scripts/                     @helix-oss/devops
pyproject.toml               @helix-oss/devops

# Test Suite
# Security-critical tests require security reviewer
tests/test_signature.py      @helix-oss/security-reviewers
tests/test_encryption.py     @helix-oss/security-reviewers
tests/test_container.py      @helix-oss/security-reviewers
tests/test_ipfs_*.py         @helix-oss/security-reviewers
tests/                       @helix-oss/qa

# Governance Documentation
CONTRIBUTING.md              @helix-oss/maintainers
CODE_OF_CONDUCT.md           @helix-oss/maintainers
SECURITY.md                  @helix-oss/security-reviewers
README.md                    @helix-oss/maintainers
```

### 3.2 チーム名ガイドライン

推奨される GitHub Teams（実装時に確認・作成）:

| チーム名 | 責務 | メンバー要件 |
|---------|------|-----------|
| `maintainers` | プロジェクト主要開発者 | senior engineer 1-2 名 |
| `security-reviewers` | 暗号化・整合性専門家 | security engineer 1 名以上 |
| `devops` | CI/DevOps・リリース | ops engineer 1 名 |
| `qa` | テストエンジニア・品質保証 | qa engineer 1 名 |

---

## 4. 実装チェックリスト

### 4.1 実装前の確認

- [ ] GitHub 組織 `helix-oss` にログイン可能
- [ ] リポジトリ admin 権限あり
- [ ] 予定するチーム名が存在するか確認（なければ作成）
- [ ] CODEOWNERS ファイルの基本構文を確認

### 4.2 ファイル作成

- [ ] `.github/CODEOWNERS` ファイルを作成
- [ ] プレースホルダー版を使用
- [ ] ローカル構文確認
- [ ] conventional commit で確定

### 4.3 検証

- [ ] GitHub Web UI でファイルが表示される
- [ ] テスト PR で自動レビューリクエストが送信される
  - `src/helix/container.py` 変更 → `@helix-oss/security-reviewers` リクエスト確認
  - `.github/workflows/ci.yml` 変更 → `@helix-oss/devops` リクエスト確認
  - その他ファイル → `@helix-oss/maintainers` リクエスト確認

---

## 5. ベストプラクティス

### 5.1 CODEOWNERS の保守性

**定期的な見直し**:
- チーム構成変更時（メンバー追加・削除）
- 新機能追加時（新モジュール追加）
- リリース時（バージョン管理体制の見直し）

### 5.2 セキュリティ上の注意

セキュリティクリティカルパスの厳格性を保つ：
- 暗号化（`container.py` HLE1 実装）
- 署名検証（`container.py` `verify_signature()` 関数）
- genome 整合性（`codec.py`, `storage.py` チャンク管理）
- IPFS 検証（`ipfs.py` ダウンロード検証）

### 5.3 GitHub リポジトリ設定の有効化

- [ ] Settings → Code and automation → Rulesets
- [ ] CODEOWNERS レビューを「Required」に設定（オプション）

---

## 6. まとめ

### 現状
- `.github/CODEOWNERS` ファイルが未作成
- PR の自動レビューリクエスト機能が inactive
- セキュリティクリティカルなファイルが誰でも修正可能

### 推奨事項
実装構成:
1. **デフォルト**: `@helix-oss/maintainers`
2. **セキュリティクリティカル**: `@helix-oss/security-reviewers`
3. **CI/DevOps**: `@helix-oss/devops`
4. **テスト**: `@helix-oss/qa`
5. **仕様**: maintainers + security-reviewers

### 実装の優先度
- **P2（中優先度）** → T-015 後に実装推奨
- **所要時間**: 30 分以内
- **リスク**: 低（GitHub validator で即座に検出可能）

### 次のステップ
1. GitHub でチーム設定を確認・作成
2. `.github/CODEOWNERS` ファイルを実装
3. テスト PR で動作確認
4. リポジトリ設定で enforce を有効化

---

**Document Status**: Ready for Implementation  
**Last Updated**: 2026-03-06
