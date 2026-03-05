# T-020: テストカバレッジ 80% 達成 — 実装計画

## 概要

T-002 で導入した pytest-cov (CI 閾値 75%) の実測値 **77% (1254/1621 stmts)** を **80% 以上** に引き上げる。
約 **43 行の Miss 削減** (367 → 324 以下) が必要。対象は cli.py (53%), perf.py (60%), diagnostics.py (75%) の 3 モジュール。

### 目標

- TOTAL カバレッジ 80% 以上
- cli.py カバレッジ 70% 以上
- CI `--cov-fail-under` を 75 → 80 に引き上げ
- 既存テスト無変更 (振る舞い変更なし)

---

## 現状分析

### モジュール別カバレッジ (低い順)

| モジュール | Stmts | Miss | Cover | テスト状況 |
|-----------|-------|------|-------|-----------|
| `__main__.py` | 3 | 3 | 0% | 未テスト (エントリポイント、影響小) |
| `cli.py` | 177 | 84 | 53% | test_doctor.py, test_keygen_cli.py, test_publish_warning.py, test_remote_pinning.py で部分カバー |
| `perf.py` | 82 | 33 | 60% | test_perf_gates.py に `evaluate_benchmark_gates` のみ 2 テスト |
| `mlhooks.py` | 159 | 49 | 69% | test_ml_hooks.py に 6 テスト |
| `pinning.py` | 108 | 34 | 69% | test_remote_pinning.py に 5 テスト |
| `diagnostics.py` | 93 | 23 | 75% | test_doctor.py に 4 テスト |

### 高カバレッジモジュール (変更不要)

| モジュール | Cover | 備考 |
|-----------|-------|------|
| `chunking.py` | 95%+ | CDC コア、十分テスト済み |
| `codec.py` | 85%+ | 統合テスト多数 |
| `container.py` | 85%+ | HLX1 パーサー、十分テスト済み |
| `storage.py` | 90%+ | SQLiteGenome、十分テスト済み |
| `errors.py` | 90%+ | 例外クラス |
| `ipfs.py` | 80%+ | IPFS 統合テスト |
| `oci.py` | 80%+ | ORAS ブリッジテスト |

---

## 影響ファイル

| ファイル | 変更種別 | 影響度 |
|----------|---------|--------|
| `tests/test_cli_commands.py` | **新規作成** | 中 (CLI コマンドテスト) |
| `tests/test_perf.py` | **新規作成** | 低 (perf プロパティ/JSON テスト) |
| `tests/test_doctor.py` | **既存拡張** | 低 (diagnostics 未カバーパス追加) |
| `.github/workflows/ci.yml` L46 | **修正** | 中 (`--cov-fail-under=75` → `80`) |

---

## 実装ステップ

### Phase 1: cli.py テスト追加 (目標: +20 行カバー → ~78.2%)

**新規ファイル**: `tests/test_cli_commands.py`

CLI テストでは `typer.testing.CliRunner` + `monkeypatch` で codec/ipfs 関数をモックし、CLI 層の UI ロジック・エラーハンドリング・出力フォーマットに集中する。

#### Step 1-1: _cfg バリデーションテスト (+4 行)

```python
# Gap 1: Lines 35-39
def test_encode_rejects_negative_chunk_size(tmp_path, monkeypatch):
    # --avg -1 → typer.BadParameter
def test_encode_rejects_invalid_chunk_ordering(tmp_path, monkeypatch):
    # --min 1000 --avg 500 → typer.BadParameter
```

#### Step 1-2: encode コマンドテスト (+15 行)

```python
# Gap 2: Lines 83-114
def test_encode_success_output_format(tmp_path, monkeypatch):
    # monkeypatch encode_file → stats 返却 → 出力確認
def test_encode_error_handling(tmp_path, monkeypatch):
    # monkeypatch encode_file → HelixError → exit_code=1
```

**モック対象**: `helix.cli.encode_file` → `EncodeStats` データクラスを返却

#### Step 1-3: decode コマンドテスト (+5 行)

```python
# Gap 3: Lines 129-138
def test_decode_success_output(tmp_path, monkeypatch):
    # monkeypatch decode_file → sha256 返却
def test_decode_error_handling(tmp_path, monkeypatch):
    # monkeypatch decode_file → HelixError
```

#### Step 1-4: verify コマンドテスト (+10 行)

```python
# Gap 4: Lines 167-197
def test_verify_success_quick_mode(tmp_path, monkeypatch):
    # monkeypatch verify_seed → ok=True, strict=False
def test_verify_success_strict_mode(tmp_path, monkeypatch):
    # monkeypatch verify_seed → ok=True, strict=True
def test_verify_failure_with_missing_chunks(tmp_path, monkeypatch):
    # monkeypatch verify_seed → ok=False, missing_count > 0
def test_verify_failure_with_sha256_mismatch(tmp_path, monkeypatch):
    # monkeypatch verify_seed → ok=False, expected/actual sha256
```

#### Step 1-5: prime コマンドテスト (+5 行)

```python
# Gap 5: Lines 210-224
def test_prime_success_output(tmp_path, monkeypatch):
    # monkeypatch prime_genome → stats dict
```

#### Step 1-6: sign コマンドテスト (+5 行)

```python
# Gap 13: Lines 501-517
def test_sign_missing_key_env(tmp_path, monkeypatch):
    # HELIX_SIGNING_KEY 未設定 → error[HELIX_E_SIGNING_KEY_MISSING]
def test_sign_success_output(tmp_path, monkeypatch):
    # monkeypatch sign_seed_file, setenv HELIX_SIGNING_KEY
```

#### Step 1-7: genome snapshot/restore テスト (+5 行)

```python
# Gap 16-17: Lines 555-559, 573-577
def test_genome_snapshot_cli_output(tmp_path, monkeypatch):
    # monkeypatch snapshot_genome → stats dict
def test_genome_restore_cli_output(tmp_path, monkeypatch):
    # monkeypatch restore_genome → stats dict
```

#### Step 1-8: fetch コマンドテスト (+3 行)

```python
# Gap 9: Lines 338-342
def test_fetch_success_output(tmp_path, monkeypatch):
    # monkeypatch fetch_seed → None (success)
def test_fetch_error_handling(tmp_path, monkeypatch):
    # monkeypatch fetch_seed → ExternalToolError
```

#### Step 1-9: export/import genes テスト (+3 行)

```python
# Gap 14-15: Lines 527-531, 542-546
def test_export_genes_cli_output(tmp_path, monkeypatch):
    # monkeypatch export_genes → stats dict
def test_import_genes_cli_output(tmp_path, monkeypatch):
    # monkeypatch import_genes → stats dict
```

**Phase 1 合計**: ~15 テスト関数、約 +20 行カバー見込み

---

### Phase 2: perf.py テスト追加 (目標: +15 行カバー → ~79.2%)

**新規ファイル**: `tests/test_perf.py`

#### Step 2-1: プロパティテスト (+3 行)

```python
# Gap 1: Line 28 (BenchCaseResult.reuse_ratio)
def test_bench_case_result_reuse_ratio_zero_chunks():
    # total_chunks=0 → 0.0
def test_bench_case_result_reuse_ratio_normal():
    # total_chunks=100, reused=75 → 0.75

# Gap 2: Line 47 (ShiftedDedupBenchmark.seed_size_ratio)
def test_shifted_dedup_benchmark_seed_size_ratio_zero_fixed():
    # fixed.seed_size_bytes=0 → 1.0
```

**モック不要**: 純粋なプロパティ計算

#### Step 2-2: JSON シリアライゼーションテスト (+10 行)

```python
# Gap 3: Lines 51-60 (to_json)
def test_shifted_dedup_benchmark_to_json():
    # JSON 出力が valid、全キー存在、sorted keys
```

**モック不要**: データクラスのメソッド呼び出し

#### Step 2-3: run_shifted_dedup_benchmark バリデーションテスト (+5 行)

```python
# Gap 5: Lines 117-141 (validation paths)
def test_run_shifted_dedup_benchmark_invalid_total_size():
    # total_size_bytes=0 → ValueError
def test_run_shifted_dedup_benchmark_invalid_offset():
    # insert_offset > total_size_bytes → ValueError
```

**モック不要**: バリデーションロジック

#### Step 2-4: _run_case 統合テスト (+10 行)

```python
# Gap 4: Lines 72-96 (codec + timing)
def test_run_shifted_dedup_benchmark_small_integration():
    # total_size_bytes=50_000 で実際に実行 (小サイズ、~1-2 秒)
    # fixed/cdc の結果検証
```

**注意**: 実際の codec を使用する統合テスト。小サイズデータ (50KB) でテスト時間を抑制。

**Phase 2 合計**: ~7 テスト関数、約 +15 行カバー見込み

---

### Phase 3: diagnostics.py テスト追加 (目標: +10 行カバー → ~79.8-80.1%)

**既存ファイル拡張**: `tests/test_doctor.py`

#### Step 3-1: IPFS CLI 成功パステスト (+3 行)

```python
# Gap 2: Lines 67-77
def test_check_ipfs_cli_success(tmp_path, monkeypatch):
    # shutil.which → "/usr/bin/ipfs"
    # subprocess.run → returncode=0, stdout="go-ipfs version 0.20.0"
    # → check.status == "ok"
```

#### Step 3-2: IPFS_PATH シナリオテスト (+4 行)

```python
# Gap 3: Lines 89-104
def test_check_ipfs_path_nonexistent(tmp_path, monkeypatch):
    # setenv IPFS_PATH → 存在しないパス → "warn"
def test_check_ipfs_path_is_file(tmp_path, monkeypatch):
    # setenv IPFS_PATH → ファイルパス → "fail"
def test_check_ipfs_path_valid_dir(tmp_path, monkeypatch):
    # setenv IPFS_PATH → 有効ディレクトリ → "ok"
```

#### Step 3-3: zstandard 検出テスト (+1 行)

```python
# Gap 7: Line 156
def test_check_compression_zstandard_available(monkeypatch):
    # find_spec → non-None → "ok"
```

#### Step 3-4: 例外ハンドリングテスト (+2 行)

```python
# Gap 8: Lines 175-178
def test_run_doctor_wraps_unexpected_exception(tmp_path, monkeypatch):
    # _check_ipfs_cli → ValueError → ExternalToolError
```

**Phase 3 合計**: ~6 テスト関数、約 +10 行カバー見込み

---

### Phase 4: CI 閾値引き上げ

#### Step 4-1: カバレッジ確認

```bash
PYTHONPATH=src uv run --no-editable python -m pytest --cov-fail-under=80
```

80% 以上を確認後に ci.yml を更新。

#### Step 4-2: ci.yml 更新

```yaml
# .github/workflows/ci.yml L46
- name: Pytest with coverage gate
  run: PYTHONPATH=src uv run --no-sync --no-editable python -m pytest --cov-fail-under=80
```

---

## 実装優先順位

| 優先度 | Phase | 対象 | カバー見込み | 累積 | 工数 |
|--------|-------|------|-------------|------|------|
| 1 | Phase 1 | cli.py | +20 行 | ~78.2% | 2h |
| 2 | Phase 2 | perf.py | +15 行 | ~79.2% | 1h |
| 3 | Phase 3 | diagnostics.py | +10 行 | ~79.8-80.1% | 1h |
| 4 | Phase 4 | ci.yml | - | 80%+ 確定 | 10min |

**合計工数**: 約 4-5 時間
**安全マージン**: +50 行目標 (43 行必要に対して余裕を持つ)

---

## テスト設計方針

### CLI テスト (test_cli_commands.py)

- **CliRunner パターン**: `typer.testing.CliRunner` で CLI コマンドを呼び出し
- **モック境界**: codec/ipfs/container 関数を `monkeypatch.setattr("helix.cli.<func>", ...)` でモック
- **検証対象**: exit_code, output テキスト, error 出力
- **既存パターン準拠**: test_keygen_cli.py, test_doctor.py と同じスタイル

```python
# 典型的な CLI テストパターン
from typer.testing import CliRunner
from helix.cli import app

def test_encode_success(tmp_path, monkeypatch):
    src = tmp_path / "input.bin"
    src.write_bytes(b"x" * 100)

    class FakeStats:
        total_chunks = 10
        reused_chunks = 5
        new_chunks = 3
        raw_chunks = 2
        unique_hashes = 8

    monkeypatch.setattr("helix.cli.encode_file", lambda **kw: FakeStats())

    runner = CliRunner()
    result = runner.invoke(app, [
        "encode", str(src),
        "--genome", str(tmp_path / "genome"),
        "--out", str(tmp_path / "seed.hlx"),
    ])
    assert result.exit_code == 0
    assert "encoded" in result.output
    assert "chunks=10" in result.output
```

### perf テスト (test_perf.py)

- **プロパティテスト**: 純粋なデータクラス計算、モック不要
- **統合テスト**: 小サイズデータ (50KB) で実際の codec を使用
- **バリデーションテスト**: ValueError の発生を検証

### diagnostics テスト (test_doctor.py 拡張)

- **subprocess モック**: `monkeypatch.setattr("helix.diagnostics.subprocess.run", ...)` で IPFS CLI をモック
- **環境変数モック**: `monkeypatch.setenv("IPFS_PATH", ...)` で IPFS_PATH を制御
- **find_spec モック**: `monkeypatch.setattr("helix.diagnostics.importlib.util.find_spec", ...)` で zstandard 検出を制御

---

## リスク評価

| リスク | 影響 | 確率 | 緩和策 |
|--------|------|------|--------|
| CLI テストのモック境界が不正確 | テストが codec 実装に依存 | 低 | codec 関数の戻り値型を正確にモック。EncodeStats 等のデータクラスを直接使用 |
| perf.py 統合テストが遅い | CI 実行時間増加 | 中 | total_size_bytes を 50,000 以下に制限 (~1-2 秒) |
| diagnostics テストで subprocess モックが脆い | Python バージョン変更で破損 | 低 | subprocess.CompletedProcess を正確に返却 |
| 80% 未到達 | CI 閾値引き上げ不可 | 低 | 余裕を持って +50 行を目標。mlhooks/pinning テスト追加をバックアップ |
| 既存テストへの影響 | テスト破損 | 極低 | 新規ファイル作成が主。test_doctor.py 拡張は関数追加のみ |

### バックアップ計画 (80% 未到達時)

Phase 3 完了後に 80% 未到達の場合:

1. **mlhooks.py (+5-10 行)**: `_stringify_metadata_value` の未テスト分岐、`_resolve_hf_cli` の各パス
2. **pinning.py (+5-10 行)**: `_parse_success` のエッジケース (空レスポンス、不正 JSON)
3. **__main__.py (+3 行)**: エントリポイントの `import` テスト

---

## 成功基準

1. `PYTHONPATH=src uv run --no-editable python -m pytest --cov-fail-under=80` がパス
2. `cli.py` のカバレッジが 70% 以上
3. 新規テスト全てパス
4. 既存 61 テスト全てパス (変更なし)
5. `ruff check .` パス
6. CI の `--cov-fail-under` が 80 に更新済み

---

## テストファイル構成

### 新規ファイル

```
tests/
├── test_cli_commands.py    # 新規: CLI コマンドテスト (~15 テスト)
├── test_perf.py            # 新規: perf.py プロパティ/統合テスト (~7 テスト)
└── test_doctor.py          # 既存拡張: diagnostics 未カバーパス (~6 テスト追加)
```

### テスト関数一覧

#### test_cli_commands.py (新規、約 15 テスト)

| # | テスト関数 | 対象 Gap | カバー行 |
|---|----------|---------|---------|
| 1 | `test_cfg_rejects_negative_sizes` | Gap 1 (L35-36) | 2 |
| 2 | `test_cfg_rejects_invalid_ordering` | Gap 1 (L37-38) | 2 |
| 3 | `test_encode_success_output` | Gap 2 (L95-112) | 8 |
| 4 | `test_encode_error_handling` | Gap 2 (L113-114) | 2 |
| 5 | `test_decode_success_output` | Gap 3 (L129-136) | 5 |
| 6 | `test_decode_error_handling` | Gap 3 (L137-138) | 2 |
| 7 | `test_verify_ok_quick_mode` | Gap 4 (L179-185) | 5 |
| 8 | `test_verify_ok_strict_mode` | Gap 4 (L179-185) | 1 |
| 9 | `test_verify_failed_with_missing` | Gap 4 (L187-197) | 5 |
| 10 | `test_prime_success_output` | Gap 5 (L210-222) | 5 |
| 11 | `test_sign_missing_key` | Gap 13 (L501-512) | 5 |
| 12 | `test_sign_success` | Gap 13 (L513-517) | 3 |
| 13 | `test_genome_snapshot_cli` | Gap 16 (L555-559) | 3 |
| 14 | `test_genome_restore_cli` | Gap 17 (L573-577) | 3 |
| 15 | `test_fetch_success` | Gap 9 (L338-342) | 3 |

#### test_perf.py (新規、約 7 テスト)

| # | テスト関数 | 対象 Gap | カバー行 |
|---|----------|---------|---------|
| 1 | `test_reuse_ratio_zero_chunks` | Gap 1 (L28) | 1 |
| 2 | `test_reuse_ratio_normal` | Gap 1 (L29) | 1 |
| 3 | `test_seed_size_ratio_zero_fixed` | Gap 2 (L47) | 1 |
| 4 | `test_to_json_valid_output` | Gap 3 (L51-60) | 10 |
| 5 | `test_benchmark_invalid_total_size` | Gap 5 (L123-124) | 2 |
| 6 | `test_benchmark_invalid_offset` | Gap 5 (L125-126) | 2 |
| 7 | `test_benchmark_small_integration` | Gap 4+5 (L72-96, 117-141) | 15 |

#### test_doctor.py (既存拡張、約 6 テスト追加)

| # | テスト関数 | 対象 Gap | カバー行 |
|---|----------|---------|---------|
| 1 | `test_ipfs_cli_success_version` | Gap 2 (L67-77) | 3 |
| 2 | `test_ipfs_path_nonexistent` | Gap 3 (L89-95) | 3 |
| 3 | `test_ipfs_path_is_file` | Gap 3 (L97-103) | 3 |
| 4 | `test_ipfs_path_valid_dir` | Gap 3 (L104) | 1 |
| 5 | `test_compression_zstandard_available` | Gap 7 (L156) | 1 |
| 6 | `test_doctor_wraps_unexpected_exception` | Gap 8 (L177-178) | 2 |

---

## Claude Code Workflow

**カテゴリ**: Test
**サイズ**: L
**ベースパターン**: `/investigate` → `/plan` → 分割実装 → `/test` → `/review` → `/commit`

| Phase | Command / Agent | 目的 |
|-------|----------------|------|
| 1. 調査 | `/investigate` | 未カバー行の詳細分析 (完了済み → docs/research/) |
| 2. 計画 | `/plan` | テスト追加計画の策定 (本ドキュメント) |
| 3a. CLI テスト | test-writer agent | `tests/test_cli_commands.py` 作成 (~15 テスト) |
| 3b. perf テスト | test-writer agent | `tests/test_perf.py` 作成 (~7 テスト) |
| 3c. diagnostics テスト | test-writer agent | `tests/test_doctor.py` 拡張 (~6 テスト追加) |
| 4. 検証 | `/test` | カバレッジ確認 (`--cov-fail-under=80`) |
| 5. CI 更新 | 直接実装 | ci.yml の閾値引き上げ |
| 6. レビュー | `/review` | テスト品質・カバレッジの確認 |
| 7. コミット | `/commit` | `test: achieve 80% coverage target (T-020)` |

**実行例**:
```
/catchup → Phase 1 (test_cli_commands.py) → /test →
Phase 2 (test_perf.py) → /test →
Phase 3 (test_doctor.py拡張) → /test →
Phase 4 (ci.yml更新) → /review → /commit
```

**注**: Phase 3a-3c は test-writer agent を順次実行。各 Phase 後に `/test` でカバレッジを確認し、80% 到達したら残りの Phase をスキップ可能。

---

## 参考資料

- 調査レポート: `docs/research/T-020_investigation.md`
- CLI カバレッジ分析: `docs/research/cli_coverage_analysis.md`
- perf カバレッジ分析: `docs/research/perf_coverage_analysis.md`
- diagnostics カバレッジ分析: `docs/research/diagnostics_coverage_gaps.md`
- テストインフラ調査: `docs/research/test_infrastructure.md`
- チケット定義: `.docs/09_リファクタリングチケット.md` (T-020 セクション)
