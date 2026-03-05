# T-015 調査レポート: Community Standards / OSS ベストプラクティス

## 1. Summary（概要）

T-015 は GitHub Community Standards の達成と、OSS コントリビューション体験の向上を目的としたチケット。
Issue / PR テンプレート、Code of Conduct（行動規範）の整備が主要スコープ。

**優先度**: P2（品質向上・保守性改善）  
**サイズ**: M（2-5ファイル、50-200行変更）  
**依存関係**: なし（独立実行可能）

現在の実測データ:
- Community Standards チェックリスト進捗: **約 40%** 達成（6/15 項目）
- 不足ファイル: Issue/PR テンプレート、Code of Conduct、GitHub Actions workflow フック

---

## 2. Current State（現状分析）

### 2.1 ✅ 既に存在するもの

| ファイル/要素 | 状態 | コメント |
|-----------|-----|---------|
| README.md | ✅ 充実 | 詳細な使用法・トラブルシューティング含む（L345） |
| LICENSE | ✅ 存在 | MIT ライセンス（LICENSE ファイル） |
| CONTRIBUTING.md | ✅ 存在 | セットアップ、開発ワークフロー記載（L43） |
| SECURITY.md | ✅ 存在 | セキュリティレポートプロセス、サポートバージョン定義（L27） |
| pyproject.toml | ✅ 完全 | プロジェクトメタデータ完備（description, license） |
| .github/workflows/ci.yml | ✅ 存在 | CI パイプライン（lint, test, compat） |
| .github/workflows/publish-seed.yml | ✅ 存在 | Publish ワークフロー |
| docs/ | ✅ 充実 | FORMAT.md, DESIGN.md, THREAT_MODEL.md, ERROR_CODES.md 等 |

**pyproject.toml メタデータ確認**:
```toml
[project]
name = "helix"
description = "Helix reference-based reconstruction with CDC and IPFS seed transport"
readme = "README.md"
requires-python = ">=3.12"
```

### 2.2 ❌ 不足しているもの

| ファイル/要素 | 必須項目 | 現状 | 優先度 |
|-----------|--------|-----|--------|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Issue テンプレート（バグ報告） | ❌ なし | **高** |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Issue テンプレート（機能リクエスト） | ❌ なし | **高** |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue テンプレート設定（ブランク無効化） | ❌ なし | 中 |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR テンプレート | ❌ なし | **高** |
| `CODE_OF_CONDUCT.md` | 行動規範（Contributor Covenant） | ❌ なし | **高** |
| `.github/FUNDING.yml` | スポンサーシップ設定 | ❌ なし | 低（T-019） |
| `CHANGELOG.md` | リリースノート | ❌ なし | 中（T-017） |
| `.github/CODEOWNERS` | コードオーナー定義 | ❌ なし | 中（T-016） |

---

## 3. Gap Analysis（ギャップ分析）

### 3.1 GitHub Community Standards チェックリスト

GitHub の "Insights → Community" ページで期待される項目と、現在のプロジェクト対応状況:

| # | 項目 | 対応状況 | 備考 |
|---|------|--------|------|
| 1 | Description | ✅ | README.md + pyproject.toml に記載 |
| 2 | README | ✅ | 詳細な README.md が存在 |
| 3 | Code of Conduct | ❌ | **CODE_OF_CONDUCT.md が未整備** |
| 4 | Contributing | ✅ | CONTRIBUTING.md が存在 |
| 5 | License | ✅ | LICENSE（MIT）が存在 |
| 6 | Security Policy | ✅ | SECURITY.md が存在 |
| 7 | Issue Template | ❌ | **Issue テンプレートが未整備** |
| 8 | Pull Request Template | ❌ | **PR テンプレートが未整備** |
| 9 | CI/CD Workflow | ✅ | GitHub Actions workflow が存在 |

**達成率**: **6/9 = 67%**（ただし GitHub 公式ダッシュボードではさらに細かな項目評価）

### 3.2 OSS ベストプラクティス（CII Best Practices Badge 基準）

| 観点 | 期待 | 現状 | ギャップ |
|-----|------|-----|---------|
| **バッジ表示** | CI, Coverage, Version | ✅ CI バッジあり（README.md L3） | Coverage バッジなし（T-020 後に可能） |
| **インストール手順** | 明確で簡潔 | ✅ 充実（L79-90） | — |
| **Quick Start** | 5分以内 | ✅ 充実（L77-140） | — |
| **API ドキュメント** | 自動生成または詳細 | ⚠️ docstring なし（T-007） | モジュール docstring 不足 |
| **テスト実行方法** | 明確 | ✅ 記載あり（README.md L295-306） | — |
| **コントリビューションガイド** | 詳細 | ✅ CONTRIBUTING.md（L43） | Issue/PR テンプレートなし |
| **セキュリティポリシー** | 明確 | ✅ SECURITY.md（L27） | — |
| **ライセンス表示** | 明確 | ✅ LICENSE 存在 | — |
| **バージョニング方針** | SemVer 明記 | ⚠️ README では「alpha」のみ | `docs/DESIGN.md` で詳細説明あり |
| **CHANGELOG** | Keep a Changelog 形式 | ❌ なし（T-017） | — |
| **Issue テンプレート** | Bug, Feature, Question | ❌ なし | **必須** |
| **PR テンプレート** | チェックリスト含む | ❌ なし | **必須** |
| **Code of Conduct** | Contributor Covenant 推奨 | ❌ なし | **必須** |

### 3.3 欠落機能の影響

#### Issue テンプレート がない影響
- **ユーザー体験**: ブランク Issue が作成され、バグ報告に必要な情報（環境、再現手順）が不足
- **メンテナー負荷**: Issue からの情報抽出に手作業が増加
- **品質**: 重複報告、不明確な報告が増加

#### PR テンプレート がない影響
- **コントリビューター体験**: PR 作成時に何をテストすべきかが不明確
- **レビュー効率**: テスト・ドキュメント・lint チェック未実施の PR が増加
- **品質**: CI パス忘れやドキュメント未更新の PR が増加

#### Code of Conduct がない影響
- **コミュニティ安全性**: 行動規範が不明確でハラスメント対応が困難
- **OSS としての成熟度**: プロフェッショナルな OSS プロジェクトとみなされない
- **法的リスク**: いかなる行動がプロジェクト除外対象かが曖昧

---

## 4. Recommendations（推奨対応）

### 4.1 **即座に対応すべき項目（優先度 HIGH）**

#### 1. Issue テンプレート（bug_report.yml）
**ファイル**: `.github/ISSUE_TEMPLATE/bug_report.yml`

**必須フィールド**:
- 環境情報（OS、Python バージョン）
- 再現手順
- 期待動作
- 実際の動作
- ログ出力/エラーメッセージ
- 添付ファイル（genome, seed 等）

**形式**: YAML form（GitHub の推奨形式）

#### 2. Feature Request テンプレート
**ファイル**: `.github/ISSUE_TEMPLATE/feature_request.yml`

**必須フィールド**:
- ユースケース（何がしたいか）
- 提案する解決策
- 代替案の検討
- 関連する既存 Issue

#### 3. Issue テンプレート設定
**ファイル**: `.github/ISSUE_TEMPLATE/config.yml`

**目的**:
- ブランク Issue の無効化
- 既存 Issue/Discussion への誘導
- 使用可能なテンプレート一覧表示

#### 4. PR テンプレート
**ファイル**: `.github/PULL_REQUEST_TEMPLATE.md`

**必須セクション**:
```markdown
## 変更概要
## 関連 Issue
## テストしたか
- [ ] Unit test 追加/更新
- [ ] 既存テスト全てパス
- [ ] ローカルで ruff check パス
- [ ] Integration test（該当時）

## ドキュメント更新
- [ ] README/docs 更新（該当時）
- [ ] CHANGELOG 更新（該当時）
```

#### 5. Code of Conduct
**ファイル**: `CODE_OF_CONDUCT.md`

**出典**: [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)

**内容**:
- 誓約（安心できるコミュニティをつくる）
- 行動基準（許容される・されない行動）
- 執行（報告プロセス、対応方法）
- 実施（Code of Conduct 委員会等の体制）

**Helix 向けカスタマイズ**:
- セキュリティセンシティブな議論でも敬意を保つこと
- 技術的な意見の相違と個人攻撃は別であること

---

### 4.2 **並行実施可能な項目（優先度 MEDIUM）**

#### 6. Issue テンプレート設定（config.yml）
- ブランク Issue 無効化で「Discussion へ」の誘導
- テンプレート選択 UX 向上

#### 7. CHANGELOG.md
**仕様**: Keep a Changelog 形式（T-017）

**初期内容**:
```markdown
# Changelog

All notable changes to this project will be documented in this file...

## [Unreleased]
- [新機能や未リリース項目]

## [1.0.0a1] - YYYY-MM-DD
### Added
- Initial alpha release
- CDC chunking (buzhash, rabin)
- IPFS integration
```

#### 8. CODEOWNERS
**目的**: セキュリティクリティカルなファイル変更時に指定レビュアーを自動アサイン

**.github/CODEOWNERS**:
```
# Security-critical paths
src/helix/container.py  @[security-reviewer]
src/helix/codec.py      @[security-reviewer]

# CI/DevOps
.github/                @[devops-reviewer]
pyproject.toml          @[devops-reviewer]

# Docs
docs/THREAT_MODEL.md    @[security-reviewer]
docs/DESIGN.md          @[maintainer]
```

---

### 4.3 **関連チケットとの統合**

T-015 実装後の依存関係:

| 関連チケット | 内容 | 実行順序 |
|------------|------|---------|
| **T-016** | CODEOWNERS 定義 | T-015 後（Issue/PR テンプレートで参照可能） |
| **T-017** | CHANGELOG + Release Notes | T-015 と並行可能 |
| **T-019** | FUNDING.yml | T-015 後（推奨） |

---

## 5. Implementation Notes（実装時の注意点）

### 5.1 Issue テンプレート の YAML form 形式

GitHub は 2024 年から YAML form ベースのテンプレートを推奨しています。
Markdown テンプレートより、構造化入力で情報抽出が容易。

**参考**: [GitHub Issue Forms - Creating templates](https://docs.github.com/en/communities/using-templates-to-guide-discussions/creating-issue-templates-for-your-repository#creating-issue-forms)

### 5.2 PR テンプレート との検証

PR マージ前に自動チェック:
- `ruff check` パス確認（GitHub Actions）
- `pytest` パス確認（GitHub Actions）
- PR テンプレートのチェックリスト項目確認（手動 or Zenhub 等の連携）

### 5.3 Code of Conduct の周知

実装後:
1. CONTRIBUTING.md から CODE_OF_CONDUCT.md への参照リンク追加
2. README.md の "Open Source Governance" セクションに追加
3. リポジトリ設定で Code of Conduct を有効化

```markdown
## Open Source Governance
- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
```

### 5.4 テンプレートのローカライズ

**日本語サポート検討**:
- GitHub Issue/PR テンプレートは 1 言語（英語推奨）でグローバル対応
- 日本語コントリビューターは GitHub 翻訳機能でサポート可能
- 日本語ドキュメントは別途 Wiki や docs/ に配置可能

### 5.5 テンプレートのテスト方法

実装後の検証:
1. テストリポジトリで Issue/PR テンプレートが表示される確認
2. YAML 形式のバリデーション確認（GitHub 側で自動実施）
3. 実際に Issue 作成して UI が正しく表示されるか確認

---

## 6. Detailed Implementation Plan（詳細実装計画）

### Phase 1: Issue テンプレート作成（高優先度）

**ファイル**: `.github/ISSUE_TEMPLATE/bug_report.yml`
**推定行数**: 30-40 行

```yaml
name: Bug Report
description: セキュリティ関連以外のバグを報告します
title: "[BUG] "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for reporting! Please provide details to help us reproduce the issue.
  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: Python version, OS, IPFS CLI version (if applicable)
      placeholder: |
        - Python: 3.12.1
        - OS: macOS 14.2
        - IPFS: v0.28.0
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: Reproduction Steps
      description: Steps to reproduce the behavior
      placeholder: |
        1. Run `helix encode input.bin --genome ./genome ...`
        2. Run `helix verify seed.hlx ...`
        3. Error occurs
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What did you expect to happen?
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
      description: What actually happened?
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Error Output / Logs
      description: Full error traceback (if any)
      render: shell
```

**ファイル**: `.github/ISSUE_TEMPLATE/feature_request.yml`
**推定行数**: 25-30 行

```yaml
name: Feature Request
description: 機能改善提案をします
title: "[FEATURE] "
labels: ["enhancement"]
body:
  - type: textarea
    id: use-case
    attributes:
      label: Use Case / Problem
      description: What problem or use case does this feature address?
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How would you like the feature to work?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Any other solutions or features you've considered?
```

### Phase 2: Issue テンプレート設定

**ファイル**: `.github/ISSUE_TEMPLATE/config.yml`
**推定行数**: 15-20 行

```yaml
blank_issues_enabled: false
contact_links:
  - name: GitHub Discussions
    url: https://github.com/helix/discussions
    about: Ask questions and share ideas here
  - name: Security Issue
    url: https://github.com/helix/security/advisories/new
    about: Report security vulnerabilities privately
```

### Phase 3: PR テンプレート

**ファイル**: `.github/PULL_REQUEST_TEMPLATE.md`
**推定行数**: 25-35 行

```markdown
## Summary
<!-- Brief description of changes -->

## Related Issue
<!-- Link to issue: Closes #123 -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Testing
- [ ] Added new tests
- [ ] Updated existing tests
- [ ] All tests pass locally
- [ ] Manual testing completed (describe below)

## Quality Checks
- [ ] `ruff check .` passes
- [ ] `pytest` passes
- [ ] No new warnings

## Documentation
- [ ] README.md updated
- [ ] docs/ updated
- [ ] CHANGELOG.md updated
- [ ] Module docstring added/updated

## Checklist
- [ ] Changes follow project style guide
- [ ] Self-review completed
- [ ] Comments added to complex sections
- [ ] No unnecessary files committed
```

### Phase 4: Code of Conduct

**ファイル**: `CODE_OF_CONDUCT.md`
**推定行数**: 70-100 行

Contributor Covenant v2.1 をベースに Helix カスタマイズを追加:

```markdown
# Contributor Covenant Code of Conduct

## Our Pledge
We as members, contributors, and leaders pledge to make participation in our
community a harassment-free experience for everyone...

## Our Standards
Examples of behavior that contributes to a positive environment:
- Using welcoming and inclusive language
- Being respectful of differing opinions, viewpoints, and experiences
- Giving and gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

Examples of unacceptable behavior:
- The use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Enforcement Responsibilities
Community leaders are responsible for clarifying and enforcing our standards...

## Scope
This Code of Conduct applies within all community spaces...

## Enforcement
Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported to the community leaders responsible for enforcement...

## Enforcement Guidelines
Community leaders will follow these Community Impact Guidelines...

## Attribution
This Code of Conduct is adapted from the Contributor Covenant, version 2.1...
```

### Phase 5: CONTRIBUTING.md の更新

CONTRIBUTING.md に Code of Conduct への参照を追加:

```markdown
# Contributing to Helix

Before contributing, please read our [Code of Conduct](CODE_OF_CONDUCT.md).

## ...（既存内容）
```

### Phase 6: README.md の更新

README.md の "Open Source Governance" セクション更新:

```markdown
## Open Source Governance
- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
```

---

## 7. Testing Strategy（テスト戦略）

### テンプレート有効性の検証

1. **手動テスト** (必須):
   - GitHub UI でテンプレートが表示されることを確認
   - Issue 作成フローで必須フィールドが要求されることを確認
   - PR テンプレートがチェックリスト形式で表示されることを確認

2. **バリデーション** (自動):
   - GitHub の YAML form バリデーション確認
   - markdown テンプレートの構文確認

3. **チェックリスト検証** (PR マージ前):
   - CI ワークフローで ruff check パス確認
   - テストパス確認

---

## 8. Acceptance Criteria（受け入れ基準）

| # | 基準 | 検証方法 |
|---|------|---------|
| 1 | Issue 作成時に Bug Report / Feature Request テンプレートが表示される | GitHub UI で確認 |
| 2 | ブランク Issue が無効化されている | GitHub Issue 作成ページで「Bug Report」「Feature Request」のみ表示 |
| 3 | PR 作成時にテンプレートが自動挿入される | GitHub PR 作成ページで確認 |
| 4 | PR テンプレートにチェックリスト（テスト・lint・ドキュメント確認）が含まれている | PR テンプレート の内容確認 |
| 5 | `CODE_OF_CONDUCT.md` が Contributor Covenant v2.1 に準拠している | ファイル内容確認 |
| 6 | `CONTRIBUTING.md` から Code of Conduct への参照リンクが存在する | リンク確認 |
| 7 | README.md の "Open Source Governance" セクションに Code of Conduct が記載されている | README.md L344-345 確認 |
| 8 | GitHub Community Standards ダッシュボードで 9/9 項目達成 | GitHub UI で確認 |

---

## 9. 推奨実行順序

```
Phase 1: Issue テンプレート（bug_report.yml, feature_request.yml）
    ↓
Phase 2: Issue テンプレート設定（config.yml）
    ↓
Phase 3: PR テンプレート
    ↓
Phase 4: Code of Conduct
    ↓
Phase 5: CONTRIBUTING.md 更新（参照リンク追加）
    ↓
Phase 6: README.md 更新（Open Source Governance セクション更新）
```

**並行実施可能**: Phase 1-3 は並行実施可能

---

## 10. 関連ドキュメント・参考資料

### GitHub 公式リソース
- [Creating issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-guide-discussions)
- [Adding a code of conduct to your project](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/adding-a-code-of-conduct-to-your-project)
- [Community Standards Insights](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions)

### OSS ベストプラクティス
- [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
- [Keep a Changelog](https://keepachangelog.com/)
- [CII Best Practices Badge](https://bestpractices.coreinfrastructure.org/)

### Helix プロジェクト内参照
- `CONTRIBUTING.md` — 開発ワークフロー
- `SECURITY.md` — セキュリティレポートプロセス
- `.claude/rules/` — プロジェクトルール

---

## 11. 実装リソース要件

| リソース | 必要性 | コメント |
|---------|-------|---------|
| 人的資源 | 1 人（6-8 時間） | テンプレート作成 + テスト検証 |
| テストリポジトリ | 推奨 | 本体マージ前に template 動作確認 |
| GitHub 管理者権限 | 不要 | テンプレートファイルは PR で提出可能 |
| 外部ツール | 不要 | GitHub 付属機能のみで対応可能 |

---

## Appendix: GitHub Community Standards チェックリスト（実装前後比較）

### Before T-015
```
✅ Description
✅ README
❌ Code of Conduct  ← T-015 で対応
✅ Contributing
✅ License
✅ Security Policy
❌ Issue Templates  ← T-015 で対応
❌ PR Template     ← T-015 で対応
✅ CI/CD Workflow

進捗: 6/9 (67%)
```

### After T-015
```
✅ Description
✅ README
✅ Code of Conduct      ← 完了
✅ Contributing
✅ License
✅ Security Policy
✅ Issue Templates      ← 完了
✅ PR Template          ← 完了
✅ CI/CD Workflow

進捗: 9/9 (100%)
```

---

## Summary Table

| 実装項目 | ファイル | 行数 | 優先度 | 依存 |
|--------|---------|------|--------|------|
| Bug Report テンプレート | `.github/ISSUE_TEMPLATE/bug_report.yml` | 40 | 高 | — |
| Feature Request テンプレート | `.github/ISSUE_TEMPLATE/feature_request.yml` | 30 | 高 | — |
| Issue テンプレート設定 | `.github/ISSUE_TEMPLATE/config.yml` | 20 | 中 | — |
| PR テンプレート | `.github/PULL_REQUEST_TEMPLATE.md` | 35 | 高 | — |
| Code of Conduct | `CODE_OF_CONDUCT.md` | 100 | 高 | — |
| CONTRIBUTING.md 更新 | `CONTRIBUTING.md` | +3 行 | 高 | — |
| README.md 更新 | `README.md` | +4 行 | 高 | — |
| **合計** | **7 ファイル** | **~230 行** | — | — |

**推定実装時間**: 4-6 時間（テンプレート作成 + テスト + コミット）

