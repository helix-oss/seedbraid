from __future__ import annotations

import sqlite3
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, Self


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


class SQLiteGenome:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                hash BLOB PRIMARY KEY,
                data BLOB NOT NULL,
                size INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def has_chunk(self, chunk_hash: bytes) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM chunks WHERE hash = ?",
            (chunk_hash,),
        )
        return cur.fetchone() is not None

    def get_chunk(self, chunk_hash: bytes) -> bytes | None:
        cur = self.conn.execute(
            "SELECT data FROM chunks WHERE hash = ?",
            (chunk_hash,),
        )
        row = cur.fetchone()
        return None if row is None else bytes(row[0])

    def put_chunk(self, chunk_hash: bytes, data: bytes) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO chunks(hash, data, size) VALUES (?, ?, ?)",
            (chunk_hash, data, len(data)),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def count_chunks(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM chunks")
        return int(cur.fetchone()[0])

    def iter_hashes(self) -> Iterator[bytes]:
        cur = self.conn.execute("SELECT hash FROM chunks")
        for (chunk_hash,) in cur:
            yield bytes(chunk_hash)

    def iter_chunks(self) -> Iterator[tuple[bytes, bytes]]:
        cur = self.conn.execute("SELECT hash, data FROM chunks ORDER BY hash")
        for chunk_hash, data in cur:
            yield bytes(chunk_hash), bytes(data)

    def clear_chunks(self) -> None:
        self.conn.execute("DELETE FROM chunks")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()


def resolve_genome_db_path(genome_path: str | Path) -> Path:
    p = Path(genome_path)
    if p.suffix in {".sqlite", ".db"}:
        return p
    return p / "genome.sqlite"


def open_genome(genome_path: str | Path) -> SQLiteGenome:
    return SQLiteGenome(resolve_genome_db_path(genome_path))
