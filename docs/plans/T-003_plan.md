# T-003: GenomeStorage Context Manager + codec.py Cleanup

**チケット**: T-003
**優先度**: P1
**カテゴリ**: CodeQuality
**サイズ**: M
**依存**: なし
**後続チケット**: T-009 (mypy), T-012 (関数分割)
**作成日**: 2026-03-06
**調査報告**: `docs/research/T-003_investigation.md`

---

## 概要と目標

`codec.py` 内の 8 関数が `try/finally: genome.close()` パターンで手動リソース管理を行っている。
Python の Context Manager プロトコル (`__enter__`/`__exit__`) を `GenomeStorage` Protocol と `SQLiteGenome` に導入し、
全 8 箇所を `with` 文に統一する。

**主な利点**:
- 可読性向上: リソースの開閉スコープが視覚化される
- 保守性向上: `finally` ブロックの手動管理が不要になる
- 型安全性: T-009 (mypy) で Context Manager Protocol の型チェックが活用できる
- Pythonic: Python 標準のリソース管理パターンに準拠

**振る舞い変更**: なし（純粋なリファクタリング）

---

## 対象ファイルと変更箇所

### 1. `src/helix/storage.py`

| 変更箇所 | 内容 | 行範囲 |
|----------|------|--------|
| import | `Self` を `typing` から追加、`types` モジュール追加 | L1-6 |
| `GenomeStorage` Protocol | `__enter__`/`__exit__` メソッド定義追加 | L9-18 |
| `SQLiteGenome` クラス | `__enter__`/`__exit__` メソッド実装追加 | L73-74 後 |

### 2. `src/helix/codec.py`

8 関数の `try/finally: genome.close()` を `with open_genome(...) as genome:` に変換:

| 関数 | 行範囲 | 複雑度 | 注意点 |
|------|--------|--------|--------|
| `encode_file()` | L75, L87, L173-174 | 低 | 直線的フロー |
| `decode_file()` | L213, L217, L223-224 | 低 | `with` 外に SHA-256 検証あり(*) |
| `verify_seed()` | L245, L250, L361-362 | 中 | 複数の early return |
| `prime_genome()` | L380, L384, L404-405 | 低 | 直線的フロー |
| `snapshot_genome()` | L409, L414, L433-434 | 低 | ネストした try/except あり |
| `restore_genome()` | L446, L450, L482-483 | 低 | ネストした with + except |
| `export_genes()` | L494, L499, L514-515 | 低 | ネストした with |
| `import_genes()` | L522, L526, L547-548 | 低 | ネストした with |

(*) `decode_file()` は `genome.close()` 後に SHA-256 検証ロジック (L226-232) がある。
このコードは `genome` を使用しないため、`with` ブロックの外に残して問題ない。

### 3. `tests/test_genome_snapshot.py` (任意)

| 変更箇所 | 内容 | 行範囲 |
|----------|------|--------|
| `test_genome_restore_replace_overwrites_existing_content` | 2 箇所の `try/finally` を `with` に変換 | L79-83, L87-91 |

テストファイル内にも同様の `try/finally: genome.close()` パターンが 2 箇所ある。
リファクタリングの一貫性のため、合わせて変換する。

---

## ステップバイステップ実装計画

### Phase 1: Protocol 拡張 (`storage.py`)

**Step 1**: import の追加

```python
# 変更前
from typing import Protocol

# 変更後
import types
from typing import Protocol, Self
```

**Step 2**: `GenomeStorage` Protocol に Context Manager メソッドを追加

```python
class GenomeStorage(Protocol):
    def has_chunk(self, chunk_hash: bytes) -> bool: ...
    def get_chunk(self, chunk_hash: bytes) -> bytes | None: ...
    def put_chunk(self, chunk_hash: bytes, data: bytes) -> bool: ...
    def count_chunks(self) -> int: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None: ...
```

**Step 3**: `SQLiteGenome` に Context Manager メソッドを実装

```python
def __enter__(self) -> SQLiteGenome:
    return self

def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: types.TracebackType | None,
) -> None:
    self.close()
```

**設計判断**:
- `__enter__` は `self` を返す（標準パターン）
- `__exit__` は例外を抑制しない（`return False` 相当 = `None` 返却）
- `Self` 型を使用（Python 3.12+ で利用可能、`from __future__ import annotations` 対応済み）
- Protocol の `__exit__` は `types.TracebackType` を使用し正確な型を定義

### Phase 2: codec.py の変換 (8 関数)

各関数について以下の変換テンプレートを適用する:

**変換パターン A** (genome スコープ内で完結する関数):

```python
# 変換前
def function_name(...) -> ReturnType:
    genome = open_genome(genome_path)
    # ... 初期化 ...
    try:
        # ... 処理 ...
        return result
    finally:
        genome.close()

# 変換後
def function_name(...) -> ReturnType:
    with open_genome(genome_path) as genome:
        # ... 初期化 ... (withスコープ内に移動)
        # ... 処理 ...
        return result
```

**変換パターン B** (`decode_file()` のように close 後にロジックがある関数):

```python
# 変換前
def decode_file(...) -> str:
    genome = open_genome(genome_path)
    h = hashlib.sha256()
    try:
        # ... genome 使用処理 ...
    finally:
        genome.close()
    # ... genome 非使用の後処理 ...
    return actual

# 変換後
def decode_file(...) -> str:
    h = hashlib.sha256()
    with open_genome(genome_path) as genome:
        # ... genome 使用処理 ...
    # ... genome 非使用の後処理 ...
    return actual
```

#### 関数別の変換詳細

**Step 4**: `encode_file()` -- パターン A

- `genome = open_genome(genome_path)` (L75) を `with open_genome(genome_path) as genome:` に変更
- L77-86 の変数初期化を `with` スコープ内に移動
- `try:` (L87) と `finally: genome.close()` (L173-174) を削除
- `with` 内のインデントを調整

**Step 5**: `decode_file()` -- パターン B

- `genome = open_genome(genome_path)` (L213) を `with open_genome(genome_path) as genome:` に変更
- `out_path = Path(out_path)` と `h = hashlib.sha256()` は `with` の前に移動
- `try:` (L217) と `finally: genome.close()` (L223-224) を削除
- L226-232 の SHA-256 検証は `with` ブロックの外に残す（genome 非使用）

**Step 6**: `verify_seed()` -- パターン A（ただし早期 return 多数）

- `genome = open_genome(genome_path)` (L245) を `with open_genome(genome_path) as genome:` に変更
- `missing`、`expected`、`expected_size` 変数は `with` の前に配置
- `try:` (L250) と `finally: genome.close()` (L361-362) を削除
- 全ての early return は `with` スコープ内なので、`__exit__` が確実に呼ばれる
- 注意: インデントレベルが 1 段増加する（既に深い箇所あり）

**Step 7**: `prime_genome()` -- パターン A

- 単純変換。カウンタ変数は `with` スコープ内に移動

**Step 8**: `snapshot_genome()` -- パターン A

- ネストした `try/except OSError` は `with genome` の内側に配置
- 構造: `with genome: ... try: ... with out: ... except OSError: ...`

**Step 9**: `restore_genome()` -- パターン A

- `try/except/finally` が 3 段構造
- 変換後は `with genome:` の内側に `try/except OSError` を配置

**Step 10**: `export_genes()` -- パターン A

- 単純変換。ネストした `with out_path.open("wb") as out:` はそのまま

**Step 11**: `import_genes()` -- パターン A

- 単純変換。ネストした `with pack_path.open("rb") as inp:` はそのまま

### Phase 3: テストファイルの変換 (任意)

**Step 12**: `tests/test_genome_snapshot.py` の 2 箇所を変換

```python
# 変換前 (L79-83)
source = open_genome(genome_a)
try:
    expected_count = source.count_chunks()
finally:
    source.close()

# 変換後
with open_genome(genome_a) as source:
    expected_count = source.count_chunks()
```

```python
# 変換前 (L87-91)
restored = open_genome(genome_b)
try:
    assert restored.count_chunks() == expected_count
finally:
    restored.close()

# 変換後
with open_genome(genome_b) as restored:
    assert restored.count_chunks() == expected_count
```

### Phase 4: 検証

**Step 13**: lint 実行

```bash
UV_CACHE_DIR=.uv-cache uv run --no-editable ruff check .
```

**Step 14**: 全テスト実行

```bash
PYTHONPATH=src uv run --no-editable python -m pytest
```

**Step 15**: コミット

```
improve: add context manager to GenomeStorage and clean up codec.py (T-003)
```

---

## リスク評価

### リスク 1: 例外処理の微妙な変化 [低]

**リスク**: `__exit__` が例外を誤って抑制する可能性
**緩和策**: `__exit__` は `None` を返す（例外を抑制しない）設計。既存テストが例外伝播をカバー。

### リスク 2: `decode_file()` の変換 [低]

**リスク**: `genome.close()` 後のコード（SHA-256 検証）が `with` ブロック内に取り込まれると、
不要な genome 保持が発生する
**緩和策**: SHA-256 検証コードは `with` ブロックの外に配置する（パターン B を適用）

### リスク 3: `restore_genome()` の try/except/finally 3段構造 [低]

**リスク**: `except OSError` の配置を誤ると例外チェーンが変化する
**緩和策**: 既存の `except` は `with genome:` の内側に配置。ネスト構造は維持。

### リスク 4: インデント増加 [低]

**リスク**: `verify_seed()` (128行) のインデントが 1 段増加し、可読性が低下する可能性
**緩和策**: T-012 (Long Function Decomposition) で分割予定。現時点では受容可能。

### リスク 5: 後方互換性 [なし]

Context Manager Protocol の追加は透過的。`genome = open_genome(...)` の使い方も引き続き動作する。
外部 API 変更なし。HLX1 フォーマット変更なし。

---

## テスト戦略

### 既存テストによる検証 (メイン)

振る舞い変更がないため、既存の全テスト (~98 テスト関数、24 ファイル) がパスすることが主要な検証手段。

**codec.py を使用するテストファイル** (12 ファイル):
- `tests/test_roundtrip.py` -- encode/decode ラウンドトリップ
- `tests/test_encryption.py` -- 暗号化付きエンコード/デコード
- `tests/test_verify_strict.py` -- 厳密検証
- `tests/test_prime_verify.py` -- prime/verify ワークフロー
- `tests/test_genome_snapshot.py` -- snapshot/restore
- `tests/test_genes_pack.py` -- export/import
- `tests/test_manifest_private.py` -- manifest_private フラグ
- `tests/test_compat_fixtures.py` -- HLX1 互換性
- `tests/test_cli_commands.py` -- CLI 経由実行
- `tests/test_dvc_bridge.py` -- DVC 統合
- `tests/test_signature.py` -- 署名検証
- `tests/test_ipfs_optional.py` -- IPFS (条件付きスキップ)

### 追加テスト (推奨)

Context Manager の基本動作を明示的に検証するテストの追加を推奨する:

```python
# tests/test_genome_snapshot.py または新規テストファイルに追加

def test_genome_context_manager(tmp_path):
    """Context Manager で open/close が正しく動作する"""
    from helix.storage import open_genome

    genome_path = tmp_path / "test.db"
    with open_genome(genome_path) as genome:
        genome.put_chunk(b"\x01" * 32, b"data")
        assert genome.has_chunk(b"\x01" * 32)
    # with 終了後、再度開いてデータが永続化されていることを確認
    with open_genome(genome_path) as genome:
        assert genome.has_chunk(b"\x01" * 32)


def test_genome_context_manager_on_exception(tmp_path):
    """例外発生時にもリソースが解放される"""
    from helix.storage import open_genome
    import pytest

    genome_path = tmp_path / "test.db"
    with pytest.raises(ValueError):
        with open_genome(genome_path) as genome:
            genome.put_chunk(b"\x01" * 32, b"data")
            raise ValueError("intentional")
    # 例外後でも再度接続可能（close されている証拠）
    with open_genome(genome_path) as genome:
        assert genome.has_chunk(b"\x01" * 32)
```

---

## ロールバック考慮

**ロールバック容易性**: 高

- 変更は 2 ソースファイル + 1 テストファイルのみ
- `git revert` で完全にロールバック可能
- 振る舞い変更がないため、ロールバック時もテストは全パスする
- Protocol への追加メソッドは透過的であり、外部互換性への影響なし

---

## 仕様への影響

| ドキュメント | 影響 |
|-------------|------|
| `docs/FORMAT.md` | なし（バイナリフォーマット変更なし） |
| `docs/DESIGN.md` | なし（アーキテクチャ変更なし） |
| `docs/THREAT_MODEL.md` | なし（セキュリティ変更なし） |
| `AGENTS.md` | なし |

---

## パフォーマンス影響

なし。Context Manager の `__enter__`/`__exit__` のオーバーヘッドは無視できるレベル。
リソース管理のタイミングに変更なし。

---

## 変更量の見積もり

| ファイル | 追加行 | 削除行 | 純増 |
|----------|--------|--------|------|
| `src/helix/storage.py` | ~15 | 0 | +15 |
| `src/helix/codec.py` | ~8 | ~24 | -16 |
| `tests/test_genome_snapshot.py` | ~4 | ~8 | -4 |
| **合計** | ~27 | ~32 | **-5** |

ネットで 5 行削減。コードが簡潔になる。

---

### Claude Code Workflow

**カテゴリ**: CodeQuality
**サイズ**: M
**ベースパターン**: `/investigate` -> `/plan` or `/refactor` -> `/test` -> `/review` -> `/commit`

| Phase | Command / Agent | 目的 |
|-------|----------------|------|
| 1. 調査 | `/investigate "GenomeStorage context manager codec.py try/finally"` | 8箇所の try/finally パターン確認 + 全体構造把握 |
| 2. 計画 | `/plan` (本ドキュメント) | 実装計画の策定 |
| 3. リファクタ | `/refactor "GenomeStorage context manager + codec.py with cleanup"` | storage.py Protocol 拡張 + codec.py 8 関数の with 変換 |
| 4. テスト | `/test` | 全テストパス確認 + Context Manager テスト追加 |
| 5. レビュー | `/review` | 変換の正確性、例外処理、型アノテーション確認 |
| 6. コミット | `/commit` | conventional commit で確定 |

**実行例**:
```
/investigate "GenomeStorage try/finally" -> /plan -> /clear -> /refactor "context manager + with cleanup" -> /test -> /review -> /commit
```

**注意事項**:
- spec-first 不要（フォーマット/アーキテクチャ変更なし）
- `/security-scan` 不要（セキュリティ影響なし）
- `/bench` 不要（パフォーマンス影響なし）
- 単一コミットで完結（M サイズ、2 ファイル変更）
