"""Hybrid genome storage with local-first IPFS fallback.

Combines a local ``GenomeStorage`` (typically
``SQLiteGenome``) with a remote ``GenomeStorage``
fallback for chunks not available locally.

Designed for decode workflows only — does not
implement ``iter_chunks`` or ``clear_chunks``.
"""

from __future__ import annotations

import types
from typing import Self

from .storage import GenomeStorage


class HybridGenomeStorage:
    """Local genome + remote fallback storage.

    Reads check local storage first. On miss, falls
    back to remote fetch. Optionally caches fetched
    chunks into local storage for future access.

    Args:
        local: Primary local genome storage.
        remote: Fallback genome storage (e.g.
            ``IPFSChunkStorage``).
        cache_fetched: Store remotely-fetched chunks
            into local genome for future reads.
    """

    def __init__(
        self,
        local: GenomeStorage,
        remote: GenomeStorage,
        *,
        cache_fetched: bool = True,
    ) -> None:
        self._local = local
        self._remote = remote
        self._cache = cache_fetched
        self._ipfs_hits = 0

    def has_chunk(
        self, chunk_hash: bytes,
    ) -> bool:
        """Check local first, then IPFS."""
        if self._local.has_chunk(chunk_hash):
            return True
        return self._remote.has_chunk(chunk_hash)

    def get_chunk(
        self, chunk_hash: bytes,
    ) -> bytes | None:
        """Get from local; fallback to IPFS.

        Caches IPFS result locally when enabled.
        """
        data = self._local.get_chunk(chunk_hash)
        if data is not None:
            return data
        data = self._remote.get_chunk(chunk_hash)
        if data is not None:
            self._ipfs_hits += 1
            if self._cache:
                self._local.put_chunk(
                    chunk_hash, data,
                )
            return data
        return None

    def put_chunk(
        self, chunk_hash: bytes, data: bytes,
    ) -> bool:
        """Store in local genome only."""
        return self._local.put_chunk(
            chunk_hash, data,
        )

    def count_chunks(self) -> int:
        """Return local chunk count."""
        return self._local.count_chunks()

    @property
    def ipfs_hit_count(self) -> int:
        """Number of chunks fetched from IPFS."""
        return self._ipfs_hits

    def close(self) -> None:
        """Close both local and remote storage."""
        self._local.close()
        self._remote.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()
