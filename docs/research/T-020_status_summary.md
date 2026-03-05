# T-020: テストカバレッジ 80% 達成 — 進捗レポート

**作成日**: 2026-03-06
**進捗**: 調査・計画策定完了、実装準備中

---

## 1. T-020の目標と現在の進捗

### 目標
- **カバレッジ**: 現在 77% (1254/1621 stmts) → **80% 以上**へ引き上げ
- **Miss 削減**: 367行 → 324行以下 (約43行削減)
- **CI 閾値**: `--cov-fail-under=75` → `--cov-fail-under=80` に引き上げ
- **既存テスト保護**: 振る舞い変更なし (61個のテストが全てパスすること)

### 現在の進捗状況
**ステータス**: ✅ 調査・計画策定完了（実装前）

- ✅ 調査フェーズ: 全6つのresearchファイルで詳細分析完了
- ✅ 計画策定: 実装計画（T-020_test_coverage_80.md）作成完了
- ⏳ 実装フェーズ: 未開始 (phase 1-4を順次実行予定)

---

## 2. 調査結果の要約

### 2.1 CLI.py カバレッジ分析
**現状**: 53% (84行未カバー)

未カバー箇所を18個のGapに分類:
| Gap | 対象 | Miss行数 | 難易度 | 見積もりカバー行 |
|-----|------|---------|--------|----------------|
| 1 | `_cfg()` バリデーション | 35-39 | 易 | 4行 |
| 2 | `encode()` (encryption/compression分岐) | 83-114 | 中 | 32行 |
| 3 | `decode()` (出力パス) | 129-138 | 易 | 10行 |
| 4 | `verify()` (strict/quick出力) | 167-197 | 中 | 31行 |
| 5 | `prime()` | 210-224 | 易 | 15行 |
| 9 | `fetch()` | 338-342 | 易 | 5行 |
| 13 | `sign()` (キー処理) | 501-517 | 易 | 17行 |
| 16-17 | `genome snapshot/restore` | 555-577 | 易 | 10行 |
| **その他** | publish/pin/genes/doctor等 | - | 中-易 | 計 +20行 |

**見積もり**: 最優先3項目(encode/verify/sign)で+20行達成見込み

### 2.2 perf.py カバレッジ分析
**現状**: 60% (33行未カバー) — テスト完全不足

未カバーを5つのGapに分類:
| Gap | 対象 | 難易度 | 見積もりカバー行 | テスト数 |
|-----|------|--------|----------------|---------|
| 1 | `BenchCaseResult.reuse_ratio` (プロパティ) | 易 | 1行 | 1 |
| 2 | `ShiftedDedupBenchmark.seed_size_ratio` | 易 | 1行 | 1 |
| 3 | `ShiftedDedupBenchmark.to_json()` | 易 | 10行 | 1 |
| 4 | `_run_case()` (codec統合) | 中 | 25行 | 2 |
| 5 | `run_shifted_dedup_benchmark()` (検証・実行) | 中 | 25行 | 8 |

**見積もり**: +50行のテストで カバレッジ 60% → 75%+を達成見込み

### 2.3 diagnostics.py カバレッジ分析
**現状**: 75% (23行未カバー)

未カバーを8つのグループに分類:
| Group | 対象 | Miss行数 | 難易度 | 見積もり |
|-------|------|---------|--------|---------|
| 1 | Python <3.12 検出 | 50 | 易 | 1行 |
| 2 | IPFS CLI 成功パス | 67-77 | 易 | 11行 |
| 3 | IPFS_PATH scenarios (3パターン) | 89-104 | 易 | 16行 |
| 4-6 | Genome パス (mkdir失敗/書き込み権限/write test失敗) | 112-132 | 中 | 6行 |
| 7 | zstandard ライブラリ検出 | 156 | 易 | 1行 |
| 8 | 例外ハンドリング (HelixError/unexpected) | 175-178 | 中 | 4行 |

**見積もり**: +10行で 100% カバレッジ達成可能

### 2.4 テストインフラストラクチャ調査
**結論**: 成熟した pytest 基盤で新テスト追加が容易

主な知見:
- ✅ 23個のテストファイル (1,768行), 61+テスト関数
- ✅ conftest.py不要: 各ファイルで独立的にfixture定義
- ✅ 共通パターン確立: CliRunner, monkeypatch, tmp_path, pytest.raises
- ✅ IPFS テスト: 自動skip機能 (ipfs CLI未インストール時)
- ✅ CI coverage gate: 75% (T-002で設定済み)

既存パターンを踏襲すれば新テスト統合は容易。

---

## 3. 実装計画の内容

**計画ファイル**: `/Users/kytk/workspace/repos/helix/docs/plans/T-020_test_coverage_80.md`

### 4フェーズ実装戦略

#### Phase 1: cli.py テスト追加 (新規ファイル: `tests/test_cli_commands.py`)
- **対象**: 約15個のテスト関数
- **見積もり**: +20行カバー → 累積 ~78.2%
- **工数**: 約2時間
- **テスト対象**:
  - `_cfg()` バリデーション (負の値, 不正な順序)
  - `encode()` (暗号化フラグ, 圧縮オプション, エラーハンドリング)
  - `decode()` (復号化キー, エラーハンドリング)
  - `verify()` (strict/quick mode, missing chunks, exit codes)
  - `prime()` (出力フォーマット, エラーハンドリング)
  - `sign()` (キー検証, 環境変数)
  - `genome snapshot/restore()` (出力フォーマット)
  - `fetch()` (パラメータ, エラーハンドリング)

#### Phase 2: perf.py テスト追加 (新規ファイル: `tests/test_perf.py`)
- **対象**: 約7個のテスト関数
- **見積もり**: +15行カバー → 累積 ~79.2%
- **工数**: 約1時間
- **テスト対象**:
  - プロパティ: `reuse_ratio()`, `seed_size_ratio()` (エッジケース)
  - JSON シリアライゼーション: `to_json()`
  - バリデーション: `total_size_bytes > 0`, `insert_offset` 境界
  - 統合: `_run_case()`, `run_shifted_dedup_benchmark()` (実際のcodec使用)

#### Phase 3: diagnostics.py テスト追加 (既存拡張: `tests/test_doctor.py`)
- **対象**: 約6個のテスト関数追加
- **見積もり**: +10行カバー → 累積 ~79.8-80.1%
- **工数**: 約1時間
- **テスト対象**:
  - IPFS CLI 成功パス
  - IPFS_PATH scenarios (nonexistent, file not dir, valid dir)
  - zstandard ライブラリ検出
  - 例外ハンドリング (HelixError wrap, unexpected exception)

#### Phase 4: CI 閾値引き上げ
- **対象**: `.github/workflows/ci.yml` L46
- **変更**: `--cov-fail-under=75` → `--cov-fail-under=80`
- **工数**: 約10分
- **前提**: Phase 1-3完了後、80% 確認済み

### テスト設計方針

**CLI テスト**:
- Typer CliRunner で実際のコマンド呼び出し
- codec/ipfs 関数を monkeypatch でモック
- 検証対象: exit_code, output テキスト, error 出力

**perf テスト**:
- プロパティ/JSON: pure計算なのでモック不要
- 統合テスト: 小サイズデータ (50KB) で実際のcodecを使用 (~1-2秒)

**diagnostics テスト**:
- subprocess モック: IPFS CLI をシミュレート
- 環境変数: monkeypatch で IPFS_PATH 制御
- find_spec モック: zstandard 検出制御

### リスク評価とバックアップ計画

| リスク | 対策 |
|--------|------|
| CLI テストのモック境界不正確 | codec 関数の戻り値型を正確にモック |
| perf.py 統合テストが遅い | total_size_bytes ≤ 50,000 に制限 |
| diagnostics テストで subprocess モック脆い | CompletedProcess を正確に返却 |
| **80% 未到達** | mlhooks/pinning テスト追加をバックアップ |

**バックアップ計画**: Phase 3後に80%未到達の場合
1. mlhooks.py (+5-10行): 未テスト分岐
2. pinning.py (+5-10行): エッジケース
3. __main__.py (+3行): エントリポイント

---

## 4. 作業の状態

### 完了項目
✅ **T-020 チケット定義**: `.docs/09_リファクタリングチケット.md` に記載
✅ **調査・分析**: 6つのresearchファイルで詳細なcoverage gap分析
✅ **実装計画**: `T-020_test_coverage_80.md` で4フェーズ計画をドキュメント化
✅ **テストインフラ調査**: 既存パターン、fixture、helper確認

### 進行中項目
⏳ **Phase 1 実装**: `tests/test_cli_commands.py` 作成予定
⏳ **Phase 2 実装**: `tests/test_perf.py` 作成予定
⏳ **Phase 3 実装**: `tests/test_doctor.py` 拡張予定

### ブロック中項目
❌ なし。すべての情報が揃っており、実装を開始できる状態

---

## 5. 次のアクションと推奨実行順序

### 即座に実行すべきアクション

#### 1. **Phase 1: CLI テスト作成** (優先度 最高)
```bash
# tests/test_cli_commands.py を作成し、以下を実装:
# - _cfg バリデーションテスト (2-4行)
# - encode コマンドテスト (8-32行)
# - decode コマンドテスト (5-10行)
# - verify コマンドテスト (5-31行)
# - prime コマンドテスト (5-15行)
# - sign コマンドテスト (3-17行)
# - genome snapshot/restore テスト (3-10行)
# - fetch コマンドテスト (3-5行)
```

**見積もり**: +20行 → カバレッジ 78.2%

#### 2. **Phase 2: perf テスト作成** (優先度 高)
```bash
# tests/test_perf.py を新規作成し、以下を実装:
# - reuse_ratio プロパティテスト (1行)
# - seed_size_ratio プロパティテスト (1行)
# - to_json() テスト (10行)
# - _run_case() 統合テスト (2個, 25行)
# - run_shifted_dedup_benchmark() テスト (8個, 25行)
```

**見積もり**: +15行 → カバレッジ 79.2%

#### 3. **Phase 3: diagnostics テスト拡張** (優先度 高)
```bash
# tests/test_doctor.py を拡張し、以下を追加:
# - IPFS CLI 成功パステスト (1個, 11行)
# - IPFS_PATH scenarios テスト (3個, 16行)
# - zstandard 検出テスト (1個, 1行)
# - 例外ハンドリングテスト (2個, 4行)
```

**見積もり**: +10行 → カバレッジ 80.1%

#### 4. **Phase 4: CI 閾値更新** (優先度 中)
```bash
# .github/workflows/ci.yml L46 を修正:
# --cov-fail-under=75 → --cov-fail-under=80
```

**見積もり**: CI gate 確定

### 検証フロー

各フェーズ後に以下を実行してカバレッジ確認:

```bash
PYTHONPATH=src uv run --no-editable python -m pytest --cov-fail-under=80
```

80% に達したら残りのフェーズをスキップ可能。

### リポジトリ状態

現在、以下の6つのuntracked filesが存在:
- `docs/plans/T-020_test_coverage_80.md` — 実装計画 (本ドキュメント)
- `docs/research/T-020_investigation.md` — 調査サマリー
- `docs/research/cli_coverage_analysis.md` — CLI gap分析 (18個のGap)
- `docs/research/diagnostics_coverage_gaps.md` — diagnostics gap分析 (8グループ)
- `docs/research/perf_coverage_analysis.md` — perf gap分析 (5つのGap)
- `docs/research/test_infrastructure.md` — テスト基盤調査

**次: 実装ファイル作成時にこれらドキュメントは .gitignore に移動またはコミットすることを検討**

---

## 補足: 成功基準

T-020 完了と認める条件:

1. ✅ `PYTHONPATH=src uv run --no-editable python -m pytest --cov-fail-under=80` がパス
2. ✅ `cli.py` のカバレッジが 70% 以上
3. ✅ 新規テスト全てパス
4. ✅ 既存 61 テスト全てパス (変更なし)
5. ✅ `ruff check .` パス
6. ✅ CI の `--cov-fail-under` が 80 に更新済み

---

## ファイル参照

| ファイル | 用途 |
|----------|------|
| `docs/plans/T-020_test_coverage_80.md` | 実装計画 (4フェーズ, リスク評価, テスト設計方針) |
| `docs/research/T-020_investigation.md` | 調査サマリー (モジュール別gap分析) |
| `docs/research/cli_coverage_analysis.md` | CLI.py 詳細gap分析 (18個のGap, 各テスト案) |
| `docs/research/perf_coverage_analysis.md` | perf.py 詳細gap分析 (5つのGap, テストコード例) |
| `docs/research/diagnostics_coverage_gaps.md` | diagnostics.py 詳細gap分析 (8グループ) |
| `docs/research/test_infrastructure.md` | テスト基盤調査 (23ファイル, パターン, 設定) |
