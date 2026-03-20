"""IPFS individual chunk publish/fetch operations.

Implements ``GenomeStorage`` Protocol backed by IPFS
``block put/get/stat`` CLI commands for distributed
chunk storage workflows.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
import types
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from typing import Self

from .chunk_manifest import ChunkEntry, ChunkManifest
from .cid import cidv1_raw_to_sha256, sha256_to_cidv1_raw
from .codec import sha256_file
from .container import read_seed
from .errors import (
    ACTION_CHECK_GENOME,
    ACTION_CHECK_IPFS_DAEMON,
    ACTION_CHECK_IPFS_NETWORK,
    ACTION_REFETCH_SEED,
    DecodeError,
    ExternalToolError,
)
from .storage import GenomeStorage


def _require_ipfs() -> str:
    ipfs = shutil.which("ipfs")
    if ipfs is None:
        raise ExternalToolError(
            "ipfs CLI not found. Install IPFS"
            " and ensure `ipfs` is on PATH.",
            code="SB_E_IPFS_NOT_FOUND",
            next_action=(
                "Install Kubo and verify"
                " with `ipfs --version`."
            ),
        )
    return ipfs


def _fetch_chunk_from_gateway(
    cid: str, gateway: str,
) -> bytes:
    """Fetch raw chunk bytes from HTTP gateway."""
    url = f"{gateway.rstrip('/')}/{cid}"
    try:
        with urllib.request.urlopen(
            url, timeout=30,
        ) as response:
            return response.read()  # type: ignore[no-any-return]
    except (
        urllib.error.URLError,
        OSError,
    ) as exc:
        raise ExternalToolError(
            "Gateway chunk fetch failed"
            f" ({url}): {exc}",
            code="SB_E_IPFS_CHUNK_GET",
            next_action=ACTION_CHECK_IPFS_NETWORK,
        ) from exc


class IPFSChunkStorage:
    """GenomeStorage backed by IPFS block operations.

    Each chunk is stored as a raw IPFS block. The
    SHA-256 digest maps deterministically to a CIDv1
    raw codec identifier.

    Args:
        gateway: Optional HTTP gateway URL for fetch
            fallback (e.g. ``https://ipfs.io/ipfs``).
        retries: Retry count for get/put operations.
        backoff_ms: Initial backoff in milliseconds.
    """

    def __init__(
        self,
        *,
        gateway: str | None = None,
        retries: int = 3,
        backoff_ms: int = 200,
    ) -> None:
        self._gateway = gateway
        self._retries = retries
        self._backoff_ms = backoff_ms
        self._published_count = 0
        self._ipfs: str | None = None

    def _ipfs_path(self) -> str:
        if self._ipfs is None:
            self._ipfs = _require_ipfs()
        return self._ipfs

    def has_chunk(
        self, chunk_hash: bytes,
    ) -> bool:
        """Check chunk availability via ipfs block stat."""
        ipfs = self._ipfs_path()
        cid = sha256_to_cidv1_raw(
            chunk_hash, is_digest=True,
        )
        proc = subprocess.run(
            [ipfs, "block", "stat", cid],
            check=False,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0

    def get_chunk(
        self, chunk_hash: bytes,
    ) -> bytes | None:
        """Fetch chunk via ipfs block get with retry.

        Falls back to HTTP gateway when configured
        and all CLI attempts fail.
        """
        ipfs = self._ipfs_path()
        cid = sha256_to_cidv1_raw(
            chunk_hash, is_digest=True,
        )
        for attempt in range(1, self._retries + 1):
            proc = subprocess.run(
                [ipfs, "block", "get", cid],
                check=False,
                capture_output=True,
            )
            if proc.returncode == 0:
                return proc.stdout
            if (
                attempt < self._retries
                and self._backoff_ms > 0
            ):
                time.sleep(
                    (
                        self._backoff_ms
                        * (2 ** (attempt - 1))
                    )
                    / 1000,
                )

        if self._gateway:
            try:
                return _fetch_chunk_from_gateway(
                    cid, self._gateway,
                )
            except ExternalToolError:
                pass

        return None

    def put_chunk(
        self, chunk_hash: bytes, data: bytes,
    ) -> bool:
        """Publish chunk via ipfs block put --cid-codec raw.

        Verifies returned CID against expected digest.
        Returns True on successful put.
        """
        ipfs = self._ipfs_path()
        expected_cid = sha256_to_cidv1_raw(
            chunk_hash, is_digest=True,
        )
        last_err = "ipfs block put failed"
        for attempt in range(1, self._retries + 1):
            proc = subprocess.run(
                [
                    ipfs, "block", "put",
                    "--cid-codec", "raw",
                ],
                input=data,
                check=False,
                capture_output=True,
            )
            if proc.returncode == 0:
                returned_cid = (
                    proc.stdout.decode(
                        "utf-8", errors="replace",
                    ).strip()
                )
                if returned_cid != expected_cid:
                    raise ExternalToolError(
                        "CID mismatch after"
                        " ipfs block put:"
                        f" expected {expected_cid},"
                        f" got {returned_cid}",
                        code="SB_E_IPFS_CHUNK_PUT",
                        next_action=(
                            ACTION_CHECK_IPFS_DAEMON
                        ),
                    )
                self._published_count += 1
                return True
            last_err = (
                proc.stderr.decode(
                    "utf-8", errors="replace",
                ).strip()
                or "ipfs block put failed"
            )
            if (
                attempt < self._retries
                and self._backoff_ms > 0
            ):
                time.sleep(
                    (
                        self._backoff_ms
                        * (2 ** (attempt - 1))
                    )
                    / 1000,
                )

        raise ExternalToolError(
            "Failed to publish chunk after"
            f" {self._retries} attempt(s):"
            f" {last_err}",
            code="SB_E_IPFS_CHUNK_PUT",
            next_action=ACTION_CHECK_IPFS_DAEMON,
        )

    def count_chunks(self) -> int:
        """Return count of chunks published in session."""
        return self._published_count

    def close(self) -> None:
        """No-op for subprocess-based storage."""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()


def publish_chunk(
    data: bytes,
    *,
    retries: int = 3,
    backoff_ms: int = 200,
) -> str:
    """Publish a single chunk to IPFS as raw block.

    Args:
        data: Raw chunk bytes.
        retries: Maximum publish attempts.
        backoff_ms: Initial backoff in milliseconds.

    Returns:
        CIDv1 string of the published block.

    Raises:
        ExternalToolError: If all attempts fail
            or CID verification fails.
    """
    chunk_hash = hashlib.sha256(data).digest()
    cid = sha256_to_cidv1_raw(
        chunk_hash, is_digest=True,
    )
    storage = IPFSChunkStorage(
        retries=retries,
        backoff_ms=backoff_ms,
    )
    storage.put_chunk(chunk_hash, data)
    return cid


def publish_chunks_from_genome(
    seed_path: Path,
    genome: GenomeStorage,
    *,
    max_workers: int = 16,
    retries: int = 3,
    backoff_ms: int = 200,
    progress_callback: (
        Callable[[int, int], None] | None
    ) = None,
) -> ChunkManifest:
    """Publish all chunks referenced by a seed to IPFS.

    Reads chunk data from the genome and publishes
    each as a raw IPFS block using ThreadPoolExecutor
    for parallelism. Deduplicates digests before
    publishing.

    Args:
        seed_path: Path to the SBD1 seed file.
        genome: Opened GenomeStorage instance.
        max_workers: Thread pool size for parallel
            publish (default 16).
        retries: Retry count per chunk publish.
        backoff_ms: Initial backoff in milliseconds.
        progress_callback: Called with
            (completed, total) after each chunk
            publishes.

    Returns:
        Populated ChunkManifest with all chunk CID
        mappings.

    Raises:
        ExternalToolError: If any chunk publish fails
            after all retries.
        DecodeError: If a chunk referenced by the seed
            is missing from genome.
    """
    seed = read_seed(seed_path)
    unique_digests = list(
        dict.fromkeys(seed.recipe.hash_table),
    )

    chunks: dict[bytes, bytes] = {}
    for digest in unique_digests:
        data = genome.get_chunk(digest)
        if data is None:
            raise DecodeError(
                "Chunk "
                f"{digest.hex()} missing"
                " from genome",
                code="SB_E_DECODE",
                next_action=ACTION_CHECK_GENOME,
            )
        chunks[digest] = data

    storage = IPFSChunkStorage(
        retries=retries,
        backoff_ms=backoff_ms,
    )
    total = len(chunks)

    with ThreadPoolExecutor(
        max_workers=max_workers,
    ) as executor:
        futures = {
            executor.submit(
                storage.put_chunk, digest, data,
            ): digest
            for digest, data in chunks.items()
        }
        completed = 0
        try:
            for future in as_completed(futures):
                future.result()
                completed += 1
                if progress_callback is not None:
                    progress_callback(
                        completed, total,
                    )
        except ExternalToolError:
            for f in futures:
                f.cancel()
            raise

    seed_sha256 = sha256_file(seed_path)
    entries = tuple(
        ChunkEntry(
            hash_hex=digest.hex(),
            cid=sha256_to_cidv1_raw(
                digest, is_digest=True,
            ),
        )
        for digest in unique_digests
    )
    return ChunkManifest(
        seed_sha256=seed_sha256,
        chunks=entries,
    )


def fetch_chunk(
    cid: str,
    *,
    retries: int = 3,
    backoff_ms: int = 200,
    gateway: str | None = None,
) -> bytes:
    """Fetch a single chunk from IPFS by CID.

    Args:
        cid: CIDv1 identifier of the chunk.
        retries: Maximum fetch attempts.
        backoff_ms: Initial backoff in milliseconds.
        gateway: Optional HTTP gateway fallback.

    Returns:
        Raw chunk bytes.

    Raises:
        ExternalToolError: If all fetch attempts
            fail.
    """
    chunk_hash = cidv1_raw_to_sha256(cid)
    storage = IPFSChunkStorage(
        gateway=gateway,
        retries=retries,
        backoff_ms=backoff_ms,
    )
    result = storage.get_chunk(chunk_hash)
    if result is None:
        raise ExternalToolError(
            f"Chunk {cid} not available"
            " after all fetch attempts",
            code="SB_E_IPFS_CHUNK_GET",
            next_action=ACTION_CHECK_IPFS_NETWORK,
        )
    return result


def fetch_chunks_parallel(
    digests: list[bytes],
    *,
    max_workers: int = 64,
    retries: int = 3,
    backoff_ms: int = 200,
    gateway: str | None = None,
    storage: IPFSChunkStorage | None = None,
) -> dict[bytes, bytes]:
    """Fetch chunks from IPFS in parallel.

    Deduplicates digests before fetching.
    Uses ThreadPoolExecutor for concurrency.

    Args:
        digests: List of 32-byte SHA-256 digests.
        max_workers: Maximum parallel threads.
        retries: Per-chunk retry count.
        backoff_ms: Per-chunk backoff base.
        gateway: Optional HTTP gateway fallback.
        storage: Shared IPFSChunkStorage instance.
            Created internally when omitted.

    Returns:
        Mapping of digest to chunk bytes.

    Raises:
        ExternalToolError: If any chunk fails
            after all retries.
    """
    unique = list(dict.fromkeys(digests))
    if not unique:
        return {}

    if storage is None:
        storage = IPFSChunkStorage(
            gateway=gateway,
            retries=retries,
            backoff_ms=backoff_ms,
        )

    def _fetch_one(
        digest: bytes,
    ) -> tuple[bytes, bytes]:
        result = storage.get_chunk(digest)
        if result is None:
            cid = sha256_to_cidv1_raw(
                digest, is_digest=True,
            )
            raise ExternalToolError(
                f"Chunk {cid} not available"
                " after all fetch attempts",
                code="SB_E_IPFS_CHUNK_GET",
                next_action=(
                    ACTION_CHECK_IPFS_NETWORK
                ),
            )
        return digest, result

    results: dict[bytes, bytes] = {}
    with ThreadPoolExecutor(
        max_workers=max_workers,
    ) as executor:
        futures = {
            executor.submit(_fetch_one, d): d
            for d in unique
        }
        try:
            for future in as_completed(futures):
                digest, data = future.result()
                results[digest] = data
        except ExternalToolError:
            for f in futures:
                f.cancel()
            raise

    return results


def fetch_decode_from_ipfs(
    seed_path: Path,
    out_path: Path,
    *,
    max_workers: int = 64,
    batch_size: int = 100,
    retries: int = 3,
    backoff_ms: int = 200,
    gateway: str | None = None,
    encryption_key: str | None = None,
    progress_callback: (
        Callable[[int, int], None] | None
    ) = None,
) -> str:
    """Decode a seed by fetching chunks from IPFS.

    Processes chunks in batches to maintain bounded
    memory usage per the streaming-first constraint.

    Args:
        seed_path: Path to the seed file.
        out_path: Destination for reconstructed file.
        max_workers: Parallel fetch threads per batch.
        batch_size: Chunks per parallel batch.
        retries: Per-chunk retry count.
        backoff_ms: Per-chunk backoff base.
        gateway: Optional HTTP gateway fallback.
        encryption_key: Passphrase for encrypted seeds.
        progress_callback: Called with
            (completed_ops, total_ops) per batch.

    Returns:
        SHA-256 hex digest of the decoded file.

    Raises:
        ExternalToolError: If chunks are unavailable.
        DecodeError: If SHA-256 verification fails.
    """
    seed = read_seed(
        seed_path, encryption_key=encryption_key,
    )
    ops = seed.recipe.ops
    hash_table = seed.recipe.hash_table
    raw_payloads = seed.raw_payloads
    total_ops = len(ops)

    h = hashlib.sha256()
    completed = 0
    shared_storage = IPFSChunkStorage(
        gateway=gateway,
        retries=retries,
        backoff_ms=backoff_ms,
    )

    with Path(out_path).open("wb") as out:
        for batch_start in range(
            0, total_ops, batch_size,
        ):
            batch_ops = ops[
                batch_start
                : batch_start + batch_size
            ]

            fetch_digests: list[bytes] = []
            for op in batch_ops:
                if op.hash_index in raw_payloads:
                    continue
                fetch_digests.append(
                    hash_table[op.hash_index],
                )

            fetched: dict[bytes, bytes] = {}
            if fetch_digests:
                fetched = fetch_chunks_parallel(
                    fetch_digests,
                    max_workers=max_workers,
                    storage=shared_storage,
                )

            for op in batch_ops:
                raw = raw_payloads.get(
                    op.hash_index,
                )
                if raw is not None:
                    chunk = raw
                else:
                    digest = hash_table[
                        op.hash_index
                    ]
                    chunk = fetched.get(digest)
                    if chunk is None:
                        raise DecodeError(
                            "Missing chunk: "
                            f"{digest.hex()}",
                            code="SB_E_DECODE",
                            next_action=(
                                ACTION_CHECK_IPFS_NETWORK
                            ),
                        )
                out.write(chunk)
                h.update(chunk)

            completed += len(batch_ops)
            if progress_callback is not None:
                progress_callback(
                    completed, total_ops,
                )

    actual = h.hexdigest()
    expected = seed.manifest.get("source_sha256")
    if expected and expected != actual:
        raise DecodeError(
            "Decoded SHA-256 mismatch: "
            f"expected {expected}, got {actual}.",
            code="SB_E_DECODE",
            next_action=ACTION_REFETCH_SEED,
        )
    return actual
