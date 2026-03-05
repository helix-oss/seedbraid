# T-015: Community Standards (Issue/PR Templates + CoC) 実装計画

## 概要・目的

GitHub Community Standards チェックリストの完全達成 (6/9 -> 9/9) を目指し、
Issue/PR テンプレートおよび Code of Conduct を整備する。
OSS としてのコントリビューション体験を向上させ、メンテナンス効率を改善する。

| 項目 | 値 |
|------|-----|
| Priority | P2 |
| Category | Community |
| Size | M (7 ファイル、約 230 行変更) |
| Dependencies | なし (独立実行可能) |

## 現状分析

### 達成済み (6/9)

| 項目 | ファイル |
|------|---------|
| Description | README.md + pyproject.toml |
| README | README.md (L345, 詳細) |
| Contributing | CONTRIBUTING.md (L43) |
| License | LICENSE (MIT) |
| Security Policy | SECURITY.md (L27) |
| CI/CD Workflow | .github/workflows/ci.yml, publish-seed.yml |

### 未達成 (3/9) -- T-015 で対応

| 項目 | 不足内容 |
|------|---------|
| Code of Conduct | CODE_OF_CONDUCT.md が存在しない |
| Issue Templates | YAML form ベースのテンプレートが存在しない |
| PR Template | PR テンプレートが存在しない |

### 既存 .github/ ディレクトリ構造

```
.github/
  workflows/
    ci.yml
    publish-seed.yml
```

テンプレート関連ファイルは一切存在しない。

---

## 実装ステップ

### Step 1: Issue テンプレート -- Bug Report (新規作成)

**ファイル**: `.github/ISSUE_TEMPLATE/bug_report.yml`
**推定行数**: 約 50 行

YAML form ベースで以下のフィールドを定義:

| フィールド | 種別 | 必須 | 内容 |
|-----------|------|------|------|
| Environment | textarea | Yes | OS, Python version, IPFS CLI version |
| Helix Version | input | Yes | `helix --version` の出力 |
| Reproduction Steps | textarea | Yes | 再現手順 |
| Expected Behavior | textarea | Yes | 期待動作 |
| Actual Behavior | textarea | Yes | 実際の動作 |
| Error Output / Logs | textarea | No | エラー出力 (render: shell) |
| Seed / Genome Info | textarea | No | 関連する seed/genome 情報 |

ラベル: `["bug", "triage"]`
タイトルプレフィックス: `[BUG] `

注意点:
- description に「セキュリティ関連は SECURITY.md を参照」の注記を入れる
- Helix 固有の情報 (chunker 設定、compression 設定等) の入力をガイド
- placeholder に具体的な `helix` コマンド例を記載

### Step 2: Issue テンプレート -- Feature Request (新規作成)

**ファイル**: `.github/ISSUE_TEMPLATE/feature_request.yml`
**推定行数**: 約 35 行

| フィールド | 種別 | 必須 | 内容 |
|-----------|------|------|------|
| Use Case / Problem | textarea | Yes | 解決したい課題 |
| Proposed Solution | textarea | Yes | 提案する解決策 |
| Alternatives Considered | textarea | No | 検討した代替案 |
| Additional Context | textarea | No | 追加情報 |

ラベル: `["enhancement"]`
タイトルプレフィックス: `[FEATURE] `

### Step 3: Issue テンプレート設定 (新規作成)

**ファイル**: `.github/ISSUE_TEMPLATE/config.yml`
**推定行数**: 約 10 行

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security Vulnerability
    url: https://github.com/{owner}/{repo}/security/advisories/new
    about: Report security vulnerabilities privately (see SECURITY.md)
  - name: General Questions
    url: https://github.com/{owner}/{repo}/discussions
    about: Ask questions and share ideas
```

注意点:
- `{owner}/{repo}` はリポジトリのオーナーに合わせて設定
- ブランク Issue を無効化し、テンプレート選択 or 外部リンクのみに誘導
- セキュリティ脆弱性は GitHub Security Advisories へ誘導 (SECURITY.md と整合)

### Step 4: PR テンプレート (新規作成)

**ファイル**: `.github/PULL_REQUEST_TEMPLATE.md`
**推定行数**: 約 35 行

セクション構成:

1. **Summary** -- 変更概要 (フリーテキスト)
2. **Related Issue** -- `Closes #123` 形式
3. **Type of Change** -- チェックボックス:
   - Bug fix
   - New feature
   - Documentation update
   - Refactoring
   - Performance improvement
   - CI/DevOps
4. **Testing Checklist** -- チェックボックス:
   - `pytest` passes locally
   - New/updated tests added
   - `ruff check .` passes
5. **Documentation Checklist** -- チェックボックス:
   - docs/ updated (if applicable)
   - FORMAT.md/DESIGN.md updated (if format/behavior change)
6. **Additional Notes** -- フリーテキスト

注意点:
- CONTRIBUTING.md の Development Workflow と整合させる
- spec-first ポリシーの確認項目を含める (FORMAT.md/DESIGN.md)
- conventional commit プレフィックスの記載は PR テンプレートではなく CONTRIBUTING.md に委ねる

### Step 5: Code of Conduct (新規作成)

**ファイル**: `CODE_OF_CONDUCT.md`
**推定行数**: 約 80 行

Contributor Covenant v2.1 をベースに作成:

1. **Our Pledge** -- ハラスメントのないコミュニティへの誓約
2. **Our Standards** -- 許容される / されない行動の具体例
3. **Enforcement Responsibilities** -- コミュニティリーダーの責務
4. **Scope** -- 適用範囲 (プロジェクト空間内)
5. **Enforcement** -- 報告方法、連絡先
6. **Enforcement Guidelines** -- 段階的対応 (Correction -> Warning -> Temporary Ban -> Permanent Ban)
7. **Attribution** -- Contributor Covenant v2.1 への帰属表記

Helix プロジェクト固有のカスタマイズ:
- 連絡先メールアドレスは `[INSERT CONTACT METHOD]` としてプレースホルダーを残す
  (リポジトリオーナーが設定時に決定)
- セキュリティセンシティブな議論でも敬意を保つことを明記

### Step 6: CONTRIBUTING.md 更新 (既存ファイル修正)

**ファイル**: `CONTRIBUTING.md`
**変更内容**: 冒頭に Code of Conduct への参照リンクを追加

```markdown
# Contributing to Helix

Thanks for contributing.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## Prerequisites
...
```

変更箇所: L1-3 の間に 1 行追加 (既存コンテンツは保持)

### Step 7: README.md 更新 (既存ファイル修正)

**ファイル**: `README.md`
**変更内容**: "Open Source Governance" セクションに Code of Conduct を追加

現在 (L341-344):
```markdown
## Open Source Governance
- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
```

変更後:
```markdown
## Open Source Governance
- License: `MIT` (`LICENSE`)
- Security policy: `SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
```

変更箇所: L345 に 1 行追加

---

## 変更対象ファイル一覧

| # | ファイル | 操作 | 推定行数 |
|---|---------|------|---------|
| 1 | `.github/ISSUE_TEMPLATE/bug_report.yml` | 新規作成 | ~50 |
| 2 | `.github/ISSUE_TEMPLATE/feature_request.yml` | 新規作成 | ~35 |
| 3 | `.github/ISSUE_TEMPLATE/config.yml` | 新規作成 | ~10 |
| 4 | `.github/PULL_REQUEST_TEMPLATE.md` | 新規作成 | ~35 |
| 5 | `CODE_OF_CONDUCT.md` | 新規作成 | ~80 |
| 6 | `CONTRIBUTING.md` | 修正 (1行追加) | +1 |
| 7 | `README.md` | 修正 (1行追加) | +1 |
| | **合計** | | **~212 行** |

---

## テスト計画

### 自動テスト

T-015 は新規ファイル追加のみでソースコード変更なし。自動テストの追加・変更は不要。

確認事項:
- `ruff check .` パス (Python ファイル変更なし、影響なし)
- `pytest` 全テストパス (変更なし、影響なし)

### 手動検証チェックリスト

| # | 検証項目 | 方法 |
|---|---------|------|
| 1 | Bug Report テンプレートが Issue 作成画面に表示される | GitHub UI: "New Issue" で確認 |
| 2 | Feature Request テンプレートが Issue 作成画面に表示される | GitHub UI: "New Issue" で確認 |
| 3 | ブランク Issue が作成できない | GitHub UI: テンプレート選択画面のみ表示 |
| 4 | Security Vulnerability リンクが表示される | GitHub UI: config.yml の contact_links 確認 |
| 5 | Bug Report の必須フィールドが入力要求される | GitHub UI: 空欄のまま Submit を試みる |
| 6 | PR テンプレートが PR 作成画面に自動挿入される | GitHub UI: "New Pull Request" で確認 |
| 7 | CODE_OF_CONDUCT.md が GitHub の Community タブに認識される | GitHub: Insights -> Community |
| 8 | CONTRIBUTING.md から CoC へのリンクが有効 | ブラウザでリンク確認 |
| 9 | README.md の Governance セクションに CoC が記載 | README.md 確認 |
| 10 | Community Standards チェックリストが 9/9 達成 | GitHub: Insights -> Community |

### YAML バリデーション

Issue テンプレートの YAML 形式は GitHub にプッシュした時点で自動バリデーションされる。
不正な場合は GitHub がテンプレートを無視する (エラー表示なし)。
プッシュ後に手動検証 #1, #2 で確認する。

---

## リスクと注意点

### リスク低

| リスク | 影響 | 対策 |
|-------|------|------|
| YAML 構文エラー | テンプレートが表示されない | プッシュ後に手動検証で確認 |
| contact_links の URL が不正 | リンク切れ | リポジトリ URL を正確に設定 |
| CoC の連絡先が未設定 | 報告先不明 | プレースホルダーを明記し、オーナーに設定を依頼 |

### 注意点

1. **リポジトリ URL**: config.yml の `contact_links` にはリポジトリの正確な URL が必要。
   `pyproject.toml` に `[project.urls]` が未設定のため、オーナー/リポジトリ名を確認して設定する。

2. **CoC 連絡先**: Contributor Covenant v2.1 では enforcement セクションに連絡先が必要。
   個人メールアドレスか、チームの共有アドレスをオーナーが決定する必要がある。
   初回コミットではプレースホルダーとし、後続 PR で確定値を設定する。

3. **言語**: テンプレートは英語で記述。日本語のコントリビューターには GitHub の翻訳機能で対応。
   プロジェクトのドキュメント (README.md, CONTRIBUTING.md, docs/) が全て英語であるため統一。

4. **既存ワークフローへの影響なし**: ソースコード変更なし、CI 設定変更なし。
   テスト・ lint への影響ゼロ。

5. **他チケットとの関連**:
   - T-016 (CODEOWNERS): T-015 完了後の推奨。PR テンプレートで CODEOWNERS への言及可能
   - T-017 (CHANGELOG): PR テンプレートの Documentation Checklist で CHANGELOG 更新を促す
   - T-019 (FUNDING.yml): 独立実行可能

---

## 完了基準

| # | 基準 | 達成確認方法 |
|---|------|------------|
| 1 | Issue 作成時に Bug Report / Feature Request のフォームテンプレートが表示される | GitHub UI |
| 2 | ブランク Issue が無効化されている | GitHub UI |
| 3 | PR 作成時にチェックリスト付きテンプレートが自動挿入される | GitHub UI |
| 4 | `CODE_OF_CONDUCT.md` が Contributor Covenant v2.1 に準拠している | ファイル内容確認 |
| 5 | `CONTRIBUTING.md` から Code of Conduct への参照リンクが存在する | リンク確認 |
| 6 | `README.md` の "Open Source Governance" セクションに CoC が記載されている | README.md 確認 |
| 7 | GitHub Community Standards チェックリストが 9/9 達成 | GitHub Insights -> Community |
| 8 | `ruff check .` パス | ローカル実行 |
| 9 | `pytest` 全テストパス | ローカル実行 |

---

## 実装順序と並行可能性

```
Step 1-3: Issue テンプレート群 (並行実施可能)
    |
    v
Step 4: PR テンプレート (並行実施可能)
    |
    v
Step 5: Code of Conduct (独立)
    |
    v
Step 6-7: CONTRIBUTING.md + README.md 更新 (Step 5 完了後)
```

Step 1-5 は相互依存なし。並行実施可能。
Step 6-7 は Step 5 (CoC 作成) の完了が前提。

推奨コミット戦略:
- 1 コミットで全 7 ファイルをまとめてコミット
- コミットメッセージ: `docs: add community standards (Issue/PR templates + CoC) (T-015)`

---

### Claude Code Workflow

| Phase | Command / Agent | 目的 |
|-------|----------------|------|
| 1. 実装 | doc-writer agent | テンプレート群 (Issue/PR/CoC) 一括生成 |
| 2. 既存ファイル更新 | 直接実装 | CONTRIBUTING.md + README.md に CoC 参照追加 |
| 3. レビュー | `/review` | テンプレート内容の妥当性・整合性確認 |
| 4. コミット | `/commit` | conventional commit で確定 |

**カテゴリ**: Community / **サイズ**: M
**ベースパターン**: `doc-writer agent -> /review -> /commit` (workflow-patterns.md Community/M)

**実行例**:
```
(doc-writer agent: 5ファイル新規作成) -> (CONTRIBUTING.md + README.md 更新) -> /review -> /commit
```

**補足**: `/investigate` は調査レポート (`docs/research/T-015-investigation.md`) が既に作成済みのため省略可能。
