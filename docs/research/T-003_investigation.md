# T-003 調査報告: GenomeStorage Context Manager + codec.py Cleanup

**日付**: 2026-03-06  
**対象**: T-003 チケット詳細分析  
**優先度**: P1  
**サイズ**: M (約 50-200 行変更)

---

## エグゼクティブサマリー

T-003 は `GenomeStorage` Protocol に Context Manager プロトコル (`__enter__`/`__exit__`) を追加し、`codec.py` の 8 関数内にある計 8 箇所の `try/finally: genome.close()` パターンを `with` 文に統一するリファクタリングチケットです。

**現在の状態**:
- `storage.py` の `GenomeStorage` Protocol に `__enter__`/`__exit__` メソッドが未定義
- `SQLiteGenome` に対応実装も未実装
- `codec.py` の 8 関数が手動リソース管理(`try/finally`)を使用
- リソース解放の意図は明確だが、Pythonic でないパターン

**変更スケール**:
- ファイル数: 2 ファイル (`storage.py`, `codec.py`)
- 変更行数: 約 30-40 行（Protocol + 実装 + try/finally → with 変換）
- テスト影響: なし（振る舞い変更なし）
- 後続チケット依存: T-009 (mypy), T-012 (関数分割)

---

## 現在の状態分析

### 1. `storage.py` の Protocol 定義 (L9-18)

```python
class GenomeStorage(Protocol):
    def has_chunk(self, chunk_hash: bytes) -> bool: ...
    def get_chunk(self, chunk_hash: bytes) -> bytes | None: ...
    def put_chunk(self, chunk_hash: bytes, data: bytes) -> bool: ...
    def count_chunks(self) -> int: ...
    def close(self) -> None: ...
```

**現状**:
- Protocol メソッドは 5 個（`has_chunk`, `get_chunk`, `put_chunk`, `count_chunks`, `close`）
- Context Manager プロトコル (`__enter__`, `__exit__`) **未定義**
- `close()` メソッドは存在するが、`with` 文では使用されていない

### 2. `SQLiteGenome` 実装 (L21-74)

```python
class SQLiteGenome:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        # ...

    def close(self) -> None:
        self.conn.close()
```

**現状**:
- Context Manager メソッド (`__enter__`, `__exit__`) **未実装**
- リソース管理は `close()` に依存
- SQLite 接続が適切に閉じられているが、Pythonic なリソース管理ではない

### 3. `codec.py` 内の 8 つの `try/finally` パターン

#### 3.1 `encode_file()` (L87-174)

```python
def encode_file(...) -> EncodeStats:
    genome = open_genome(genome_path)
    # ...
    try:
        for chunk in _chunk_stream_from_file(in_path, chunker, cfg):
            # チャンク処理ロジック
            # ...
        return stats
    finally:
        genome.close()  # L173-174
```

**特徴**:
- `try` ブロック: チャンク処理とシード書き込み
- `finally` ブロック: genome の明示的なクローズ
- 例外発生時にも確実に `close()` が呼ばれる（現在も安全）

#### 3.2 `decode_file()` (L217-224)

```python
def decode_file(...) -> str:
    genome = open_genome(genome_path)
    # ...
    try:
        with out_path.open("wb") as out:
            for op in seed.recipe.ops:
                chunk = _resolve_chunk(...)
                # ...
    finally:
        genome.close()  # L223-224
```

**特徴**:
- 出力ファイルは既に `with` で管理されている
- genome だけが `finally` で手動管理

#### 3.3 `verify_seed()` (L250-362)

```python
def verify_seed(...) -> VerifyReport:
    genome = open_genome(genome_path)
    # ...
    try:
        # 署名検証、レシピ検証、チャンク検証の複雑なロジック
        # 多数の early return がある
        return VerifyReport(...)
    finally:
        genome.close()  # L361-362
```

**特徴**:
- 最も複雑な関数（~128 行）
- 複数の early return パス
- genome クローズは全パスで保証される必要がある

#### 3.4 `prime_genome()` (L384-405)

```python
def prime_genome(...) -> dict[str, int]:
    genome = open_genome(genome_path)
    # ...
    try:
        for file_path in files:
            for chunk in _chunk_stream_from_file(file_path, chunker, cfg):
                # チャンク処理
        return {...}
    finally:
        genome.close()  # L404-405
```

#### 3.5 `snapshot_genome()` (L414-434)

```python
def snapshot_genome(genome_path: str | Path, out_path: str | Path) -> dict[str, int]:
    genome = open_genome(genome_path)
    # ...
    try:
        # genome.iter_chunks() の処理
        # OSError キャッチ
    finally:
        genome.close()  # L433-434
```

**特徴**:
- `genome.iter_chunks()` を使用
- OSError の処理あり

#### 3.6 `restore_genome()` (L450-483)

```python
def restore_genome(...) -> dict[str, int]:
    genome = open_genome(genome_path)
    # ...
    try:
        with snapshot_path.open("rb") as inp:
            # ヘッダ検証とチャンク復元
    except OSError as exc:
        raise HelixError(...) from exc
    finally:
        genome.close()  # L482-483
```

**特徴**:
- 入力ファイルは `with` で管理
- genome のクローズは `finally` で

#### 3.7 `export_genes()` (L499-515)

```python
def export_genes(...) -> dict[str, int]:
    genome = open_genome(genome_path)
    # ...
    try:
        with out_path.open("wb") as out:
            for digest in seed.recipe.hash_table:
                chunk = genome.get_chunk(digest)
                # ...
    finally:
        genome.close()  # L514-515
```

#### 3.8 `import_genes()` (L526-548)

```python
def import_genes(...) -> dict[str, int]:
    genome = open_genome(genome_path)
    # ...
    try:
        with pack_path.open("rb") as inp:
            # チャンク復元ロジック
    finally:
        genome.close()  # L547-548
```

---

## 影響範囲の詳細分析

### 2.1 ファイル一覧と変更箇所

| ファイル | 行範囲 | 変更内容 | 複雑度 |
|----------|--------|---------|--------|
| `src/helix/storage.py` | L9-18 | Protocol に `__enter__`/`__exit__` 追加 | 低 |
| `src/helix/storage.py` | L21-74 | SQLiteGenome に `__enter__`/`__exit__` 実装 | 低 |
| `src/helix/codec.py` | L87-174 | `encode_file()` の try/finally → with | 低 |
| `src/helix/codec.py` | L217-224 | `decode_file()` の try/finally → with | 低 |
| `src/helix/codec.py` | L250-362 | `verify_seed()` の try/finally → with | 中 |
| `src/helix/codec.py` | L384-405 | `prime_genome()` の try/finally → with | 低 |
| `src/helix/codec.py` | L414-434 | `snapshot_genome()` の try/finally → with | 低 |
| `src/helix/codec.py` | L450-483 | `restore_genome()` の try/finally → with | 低 |
| `src/helix/codec.py` | L499-515 | `export_genes()` の try/finally → with | 低 |
| `src/helix/codec.py` | L526-548 | `import_genes()` の try/finally → with | 低 |

### 2.2 テスト対象

**テストファイル**（12 ファイル codec.py を使用）:
- `tests/test_roundtrip.py` — encode/decode ラウンドトリップ
- `tests/test_encryption.py` — 暗号化付きエンコード/デコード
- `tests/test_verify_strict.py` — 厳密検証
- `tests/test_prime_verify.py` — prime/verify ワークフロー
- `tests/test_genome_snapshot.py` — snapshot/restore 関数
- `tests/test_genes_pack.py` — export/import 関数
- `tests/test_manifest_private.py` — manifest_private フラグ
- `tests/test_compat_fixtures.py` — 互換性テスト
- `tests/test_cli_commands.py` — CLI 経由での実行
- `tests/test_dvc_bridge.py` — DVC 統合
- `tests/test_signature.py` — 署名検証
- `tests/test_ipfs_optional.py` — IPFS publish/fetch

**期待される結果**: 全テストパス（振る舞い変更なし）

### 2.3 CLI/外部利用

**`cli.py` でのインポート**:
```python
from .codec import (
    decode_file, encode_file, export_genes, import_genes,
    prime_genome, restore_genome, snapshot_genome, verify_seed,
)
```

**各コマンド**:
- `helix encode` → `encode_file()`
- `helix decode` → `decode_file()`
- `helix verify` → `verify_seed()`
- `helix prime` → `prime_genome()`
- `helix genome snapshot` → `snapshot_genome()`
- `helix genome restore` → `restore_genome()`
- `helix export-genes` → `export_genes()`
- `helix import-genes` → `import_genes()`

**重要**: CLI は例外ハンドリングを行っており、`with` への変更は透過的

---

## リソースリーク/安全性分析

### 現在の状態（リスク評価）

| シナリオ | 現在 | リスク |
|--------|------|--------|
| 正常系（return）| `finally` で close 実行 | ✅ 安全 |
| 例外発生（try 内）| `finally` で close 実行 | ✅ 安全 |
| KeyboardInterrupt | `finally` で close 実行 | ✅ 安全 |
| 複数 early return | 各 return パスで close 実行 | ✅ 安全 |

**結論**: 現在の実装は既に安全です。`with` への移行は**可読性と Pythonic さの向上**が主な利点。

### `with` 移行後（改善点）

1. **可読性向上**: リソース開閉が局所化され、スコープが明確
2. **保守性向上**: インデント構造でリソース生存期間が視覚化
3. **例外チェーン**: Context Manager の例外処理は例外を抑制しない（`__exit__` で `False` 返却）
4. **型安全性**: T-009 (mypy) で型チェック時に Context Manager Protocol が活用される

---

## Protocol 変更の詳細設計

### Protocol への追加メソッド

```python
from typing import Self

class GenomeStorage(Protocol):
    def has_chunk(self, chunk_hash: bytes) -> bool: ...
    def get_chunk(self, chunk_hash: bytes) -> bytes | None: ...
    def put_chunk(self, chunk_hash: bytes, data: bytes) -> bool: ...
    def count_chunks(self) -> int: ...
    def close(self) -> None: ...
    
    # 新規追加
    def __enter__(self) -> Self: ...
    def __exit__(
        self, 
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None: ...
```

**注意**:
- Python 3.12+ の `Self` 型を使用（`from typing import Self`）
- `__exit__` は例外を抑制しない（`return False` または `return None`）
- `types.TracebackType` import が必要

### SQLiteGenome への実装

```python
class SQLiteGenome:
    # ... 既存コード ...
    
    def __enter__(self) -> SQLiteGenome:
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
```

**設計の根拠**:
- `__enter__` は `self` を返す（標準パターン）
- `__exit__` は `self.close()` を呼ぶ（リソース解放）
- 例外を抑制しない（`return False` 相当）

---

## 実装手順の詳細

### Phase 1: Protocol 拡張（`storage.py`）

1. **L1 の import 確認**:
   ```python
   from __future__ import annotations
   from typing import Protocol, Self  # Self を追加
   ```

2. **Protocol へのメソッド追加** (L9-18 後):
   ```python
   class GenomeStorage(Protocol):
       # ... 既存 5 メソッド ...
       
       def __enter__(self) -> Self: ...
       def __exit__(
           self,
           exc_type: type[BaseException] | None,
           exc_val: BaseException | None,
           exc_tb: types.TracebackType | None,
       ) -> None: ...
   ```

3. **types import が必要な場合**:
   ```python
   import types  # Protocol の __exit__ シグネチャ用
   ```

### Phase 2: SQLiteGenome への実装（`storage.py`）

1. **`close()` メソッドの直後に追加** (L73-74 後):
   ```python
   def __enter__(self) -> SQLiteGenome:
       return self
   
   def __exit__(self, exc_type, exc_val, exc_tb) -> None:
       self.close()
   ```

### Phase 3: codec.py の 8 関数を `with` に変換

#### テンプレート変換パターン

**Before**:
```python
def function_name(...) -> ReturnType:
    genome = open_genome(genome_path)
    # ... 初期化 ...
    try:
        # ... 処理ロジック ...
        return result
    finally:
        genome.close()
```

**After**:
```python
def function_name(...) -> ReturnType:
    with open_genome(genome_path) as genome:
        # ... 処理ロジック ...
        return result
```

#### 変換の注意点

| 関数 | 注意点 | 処置 |
|------|--------|------|
| `encode_file()` | 直線的な処理フロー | 単純変換可能 |
| `decode_file()` | 出力ファイルも `with` で管理 | ネスト可能、問題なし |
| `verify_seed()` | 多数の early return | `with` スコープ内なら全て保護される |
| `prime_genome()` | シンプル | 単純変換可能 |
| `snapshot_genome()` | 出力ファイル + OSError 処理 | ネスト可能 |
| `restore_genome()` | 入力ファイル + OSError 処理 | ネスト可能 |
| `export_genes()` | 出力ファイル | ネスト可能 |
| `import_genes()` | 入力ファイル | ネスト可能 |

---

## verify_seed() の詳細（最も複雑な関数）

**現在の構造** (L250-362):

```python
def verify_seed(...) -> VerifyReport:
    seed = read_seed(...)
    genome = open_genome(genome_path)
    # ... 初期化 ...
    
    try:
        # ブロック 1: 署名検証 (L251-281)
        if require_signature and seed.signature is None:
            return VerifyReport(...)
        if seed.signature is not None:
            if signature_key is None:
                if require_signature:
                    return VerifyReport(...)
            else:
                ok, sig_reason = verify_signature(seed, signature_key)
                if not ok:
                    return VerifyReport(...)
        
        # ブロック 2: レシピ検証 (L283-310)
        for op in seed.recipe.ops:
            if op.hash_index >= len(seed.recipe.hash_table):
                return VerifyReport(...)
            digest = seed.recipe.hash_table[op.hash_index]
            has_genome = genome.has_chunk(digest)
            has_raw = op.hash_index in seed.raw_payloads
            if op.opcode == OP_REF and not (has_genome or has_raw):
                missing.append(digest.hex())
            if op.opcode == OP_RAW and not (has_raw or has_genome):
                missing.append(digest.hex())
        
        if missing:
            unique_missing = sorted(set(missing))
            return VerifyReport(...)
        
        # ブロック 3: 非厳密モード (L312-320)
        if not strict:
            return VerifyReport(...)
        
        # ブロック 4: 厳密モード検証 (L322-351)
        h = hashlib.sha256()
        actual_size = 0
        for op in seed.recipe.ops:
            chunk = _resolve_chunk(...)
            h.update(chunk)
            actual_size += len(chunk)
        
        if isinstance(expected_size, int) and expected_size != actual_size:
            return VerifyReport(...)
        
        actual = h.hexdigest()
        if expected and expected != actual:
            return VerifyReport(...)
        
        return VerifyReport(...)
    finally:
        genome.close()
```

**`with` への変換**:

```python
def verify_seed(...) -> VerifyReport:
    seed = read_seed(...)
    missing: list[str] = []
    # ... 初期化 ...
    
    with open_genome(genome_path) as genome:
        # ブロック 1-4 は同一（インデント増加）
        # ...すべての early return は `with` スコープ内
        # ...genome.close() は `with` の終了時に自動実行
```

**利点**:
- 4 つの early return パスすべてで確実に genome が close される
- 7 行の `try/finally` 構文が不要になる
- `genome` の生存期間が明確になる

---

## リスク評価と緩和策

### リスク 1: 型チェック（T-009 依存）

**リスク**: Protocol に `__enter__`/`__exit__` を追加した場合、T-009 (mypy) の導入時に型チェック失敗の可能性

**緩和策**:
- `__exit__` のシグネチャは正確に実装
- `Self` 型を使用（Python 3.12+ で利用可能）

### リスク 2: 例外処理の微妙な変化

**リスク**: `__exit__` が例外を抑制する場合（`return True`）、既存の例外伝播に影響

**緩和策**:
- 設計通り `__exit__` は例外を抑制しない
- テストで確認（既存テストで例外ハンドリングをカバー）

### リスク 3: 後方互換性

**リスク**: `open_genome()` の戻り値に Context Manager Protocol を期待する外部コード

**現状**: 
- Helix は内部使用のみ（チケット T-016 CODEOWNERS で明示）
- 外部 API として公開されていない

**緩和策**: Context Manager Protocol 追加は透過的（既存コードも動作継続）

---

## テスト戦略

### 1. 既存テストの実行確認

```bash
PYTHONPATH=src uv run --no-editable python -m pytest
```

**期待**: 全テストパス（振る舞い変更なし）

### 2. Context Manager 動作確認テスト（追加可能）

```python
def test_genome_context_manager(tmp_path):
    genome_path = tmp_path / "test.db"
    
    # Context Manager での使用
    with open_genome(genome_path) as genome:
        assert isinstance(genome, SQLiteGenome)
        genome.put_chunk(b"hash", b"data")
        assert genome.has_chunk(b"hash")
    
    # 再度開いて確認
    with open_genome(genome_path) as genome:
        assert genome.has_chunk(b"hash")  # データが保存されている

def test_genome_context_manager_exception(tmp_path):
    genome_path = tmp_path / "test.db"
    
    with pytest.raises(ValueError):
        with open_genome(genome_path) as genome:
            genome.put_chunk(b"hash", b"data")
            raise ValueError("test error")
    
    # 例外発生後も genome は close されている
    with open_genome(genome_path) as genome:
        assert genome.has_chunk(b"hash")
```

**オプション**: 既存テストのみで十分（振る舞い変更がないため）

---

## 実装チェックリスト

### storage.py の変更

- [ ] L1-6: `from typing import Self` を import に追加
- [ ] `import types` を追加（`__exit__` シグネチャ用）
- [ ] Protocol L9-18 に `__enter__`/`__exit__` メソッドを追加
- [ ] SQLiteGenome L73-74 後に `__enter__` と `__exit__` メソッドを実装
- [ ] 全メソッドの型アノテーションを確認

### codec.py の変更（8 箇所）

#### 関数ごとのチェック

**encode_file() (L87-174)**
- [ ] L75 の `genome = open_genome(genome_path)` → `with open_genome(...) as genome:`
- [ ] L87 の `try:` 削除
- [ ] L173-174 の `finally: genome.close()` 削除
- [ ] インデント調整

**decode_file() (L217-224)**
- [ ] L213 の `genome = open_genome(genome_path)` → `with open_genome(...) as genome:`
- [ ] L217 の `try:` 削除
- [ ] L223-224 の `finally: genome.close()` 削除
- [ ] インデント調整

**verify_seed() (L250-362)**
- [ ] L245 の `genome = open_genome(genome_path)` → `with open_genome(...) as genome:`
- [ ] L250 の `try:` 削除
- [ ] L361-362 の `finally: genome.close()` 削除
- [ ] インデント調整（複雑性が高いため丁寧に）

**prime_genome() (L384-405)**
- [ ] 同様の変換

**snapshot_genome() (L414-434)**
- [ ] 同様の変換

**restore_genome() (L450-483)**
- [ ] 同様の変換

**export_genes() (L499-515)**
- [ ] 同様の変換

**import_genes() (L526-548)**
- [ ] 同様の変換

### テスト確認

- [ ] `ruff check .` パス確認
- [ ] `PYTHONPATH=src uv run --no-editable python -m pytest` 全テストパス確認
- [ ] CLI コマンドの動作確認（オプション）

---

## 推奨実装順序

1. **storage.py を完成**: Protocol + SQLiteGenome 実装
2. **codec.py を变換**: 関数ごとに変換し、都度テスト
3. **全テスト実行**: 最終確認

**並列化**: storage.py と codec.py の変更は独立しているため、同時進行可能。

---

## 関連チケット依存関係

### 先行チケット
- **T-001** (Version Single Source of Truth): 完了 ✅
- **T-002** (pytest-cov): 完了 ✅
- **T-004** (decrypt_seed_bytes Double scrypt Fix): 完了 ✅
- **T-020** (Test Coverage Improvement): 完了 ✅

### 後続チケット
- **T-009** (Static Type Checking with mypy): 本チケット完了後に T-009 を開始（Protocol 型定義が活用される）
- **T-012** (Long Function Decomposition): 本チケット完了後に推奨（コード構造が確定後に分割）
- **T-006** (Add next_action to Error Raises): 独立（並列可能）

---

## 仕様への影響

**FORMAT.md**: 変更なし（バイナリフォーマットに影響なし）

**DESIGN.md**: 変更なし（アーキテクチャに影響なし）

**THREAT_MODEL.md**: 変更なし（セキュリティに影響なし）

---

## パフォーマンス影響

**期待**: なし

- Context Manager の `__enter__`/`__exit__` はオーバーヘッド最小限
- リソース管理のタイミング変わらず

---

## 復習と確認事項

### 変更前後の比較

**変更前** (現在):
```python
def encode_file(...) -> EncodeStats:
    genome = open_genome(genome_path)
    try:
        # ... 処理 ...
        return stats
    finally:
        genome.close()
```

**変更後** (リファクタリング後):
```python
def encode_file(...) -> EncodeStats:
    with open_genome(genome_path) as genome:
        # ... 処理 ...
        return stats
```

**利点**:
- ✅ Pythonic: Context Manager パターン
- ✅ 可読性向上: リソース開閉が視覚化
- ✅ 保守性向上: スコープが明確
- ✅ 型安全性向上: T-009 で mypy チェック可能

---

## 最終チェック項目

| 項目 | 状態 | 確認 |
|------|------|------|
| Protocol 定義完成 | 実装前 | 後述 |
| SQLiteGenome 実装完成 | 実装前 | 後述 |
| 8 関数の変換完成 | 実装前 | 後述 |
| 全テストパス | 実装前 | 後述 |
| ruff check パス | 実装前 | 後述 |
| ドキュメント更新不要 | ✅ 確認 | FORMAT.md, DESIGN.md に影響なし |

---

## まとめ

T-003 は Helix のリソース管理を Pythonic な Context Manager パターンに統一する、重要だが実装範囲が限定的なリファクタリングです。

**推奨アクション**: 
1. storage.py を先に完成
2. codec.py を関数ごとに段階的に変換
3. 全テスト確認後にコミット

**推定作業時間**: 1-2 時間（設計込み）

**リスク**: 低（振る舞い変更なし、既存テストがカバー）

