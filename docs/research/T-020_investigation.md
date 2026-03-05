# T-020 調査レポート: Test Coverage Improvement (Target 80%)

## 現状

| 指標 | 値 |
|------|-----|
| 現在カバレッジ | **77% (1254/1621 stmts)** |
| 目標 | **80%** |
| 必要 Miss 削減数 | **~43行** (367 → 324以下) |
| CI閾値 | 75% (T-002で設定済み) |

## モジュール別カバレッジ (低い順)

| モジュール | Stmts | Miss | Cover | テスト難易度 | 優先度 |
|-----------|-------|------|-------|-------------|--------|
| `__main__.py` | 3 | 3 | 0% | 低(3行) | 低 |
| `cli.py` | 177 | 84 | 53% | 中 | **最高** |
| `perf.py` | 82 | 33 | 60% | 易〜中 | **高** |
| `mlhooks.py` | 159 | 49 | 69% | 中〜難 | 中 |
| `pinning.py` | 108 | 34 | 69% | 中 | 中 |
| `diagnostics.py` | 93 | 23 | 75% | 易 | **高** |

## 攻略戦略

### 必要量: 43行 → 以下3モジュールで達成可能

### Phase 1: cli.py (最大インパクト、目標+20行)

**現状**: 53% (84 miss)。CliRunnerベースのテストが一部存在するが主要コマンドの異常系・オプション分岐が未カバー。

**未カバー主要箇所**:
| Gap | コマンド | Missing行 | 行数 | 難易度 |
|-----|---------|-----------|------|--------|
| 1 | `_cfg()` helper | 35-39 | 5 | 易 |
| 2 | `encode` (暗号化/圧縮分岐) | 83-114 | 32 | 中 |
| 3 | `decode` (出力パス処理) | 129-138 | 10 | 易 |
| 4 | `verify` (strict/quick出力) | 167-197 | 31 | 中 |
| 5 | `prime` | 210-224 | 15 | 易 |
| 6-7 | `publish`/`fetch` | 284-305 | 10 | 中(IPFS mock) |
| 8-9 | `snapshot`/`restore` | 338-351 | 8 | 易 |
| 10 | `sign` | 501-517 | 17 | 易 |
| 11-12 | `pin`/`unpin` | 527-577 | 20 | 中(mock) |
| 13 | `gene export/import` | 590-591 | 2 | 易 |

**テスト戦略**:
- `typer.testing.CliRunner` で主要コマンドの正常系をテスト
- codec/ipfs関数をmonkeypatchでモック (CLI層のUI/エラーパスに集中)
- encode/verify/sign の3コマンドで20行以上カバー見込み

### Phase 2: perf.py (+15行)

**現状**: 60% (33 miss)。テストファイル `tests/test_perf.py` が存在しない。

**未カバー箇所**:
| Gap | 関数 | Missing行 | 行数 | 難易度 |
|-----|------|-----------|------|--------|
| 1 | `BenchCaseResult.reuse_ratio` | 28 | 1 | 易 |
| 2 | `ShiftedDedupBenchmark.seed_size_ratio` | 47 | 1 | 易 |
| 3 | `ShiftedDedupBenchmark.to_json()` | 51-60 | 10 | 易 |
| 4 | `_run_case()` | 72-96 | 25 | 中(codecモック) |
| 5 | `run_shifted_dedup_benchmark()` | 117-141 | 25 | 中(codecモック) |

**テスト戦略**:
- Phase 2a: プロパティ/JSON (Gap 1-3) → モック不要、3テストで12行カバー
- Phase 2b: `_run_case` / `run_shifted_dedup_benchmark` → codec関数モックで15-20行追加

### Phase 3: diagnostics.py (+10行)

**現状**: 75% (23 miss)。既存 `tests/test_diagnostics.py` あり。

**未カバー箇所**:
| Gap | 関数 | Missing行 | 行数 | 難易度 |
|-----|------|-----------|------|--------|
| 1 | Python version check | 50 | 1 | 易 |
| 2 | IPFS CLI success path | 67-77 | 11 | 易(subprocess mock) |
| 3 | IPFS_PATH scenarios | 89-104 | 16 | 易(tmp_path) |
| 4 | Genome mkdir error | 112-113 | 2 | 中 |
| 5 | Genome permission | 121 | 1 | 中 |
| 6 | Compression check | 156 | 1 | 易 |
| 7 | Exception handling | 175-178 | 4 | 中 |

**テスト戦略**:
- IPFS CLI成功パス + IPFS_PATH + 圧縮チェックで10行カバー
- monkeypatch + tmp_path で十分テスト可能

## 見積りまとめ

| Phase | 対象 | カバー見込み | 累積カバレッジ |
|-------|------|-------------|---------------|
| 1 | cli.py | +20行 | ~78.2% |
| 2 | perf.py | +15行 | ~79.2% |
| 3 | diagnostics.py | +10行 | ~79.8% |
| **合計** | | **+45行** | **~80.1%** |

**注**: 実際のカバレッジは分岐の実行パスに依存するため、余裕を持って+50行を目標とする。

## テストインフラ

- **conftest.py**: なし (各テストファイルが独立)
- **共通パターン**: `tmp_path`, `monkeypatch`, `CliRunner`, `pytest.raises`
- **CLI テスト**: `typer.testing.CliRunner` (test_cli.py に既存パターンあり)
- **フィクスチャ**: `tests/fixtures/compat/v1/` にcompat用小ファイルあり
- **pytest設定**: `pyproject.toml` に `addopts = "--cov=helix --cov-report=term-missing"`

## 実装計画

1. **tests/test_cli_commands.py** (新規): CLI コマンドテスト (encode/verify/sign/prime/snapshot/restore)
2. **tests/test_perf.py** (新規): perf.py のプロパティ/JSON/ベンチマーク関数テスト
3. **tests/test_diagnostics.py** (既存拡張): 未カバー診断パスの追加テスト
4. **ci.yml**: `--cov-fail-under=75` → `--cov-fail-under=80` に引き上げ

## リスク

- cli.py のテストはcodec関数のモックが必要 → モック境界の設計が重要
- IPFS依存テストはIPFS CLIのモックで対応 (実IPFS不要)
- perf.pyの`_run_case`はファイルI/O + codec統合 → tmp_path + モック併用
