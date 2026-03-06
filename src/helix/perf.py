from __future__ import annotations

import json
import random
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .chunking import ChunkerConfig
from .codec import encode_file, prime_genome


@dataclass(frozen=True)
class BenchCaseResult:
    chunker: str
    total_chunks: int
    reused_chunks: int
    new_chunks: int
    seed_size_bytes: int
    prime_seconds: float
    encode_seconds: float
    encode_throughput_mib_s: float

    @property
    def reuse_ratio(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.reused_chunks / self.total_chunks


@dataclass(frozen=True)
class ShiftedDedupBenchmark:
    source_size_bytes: int
    insert_offset: int
    inserted_size_bytes: int
    fixed: BenchCaseResult
    cdc: BenchCaseResult

    @property
    def reuse_improvement_bps(self) -> int:
        return int((self.cdc.reuse_ratio - self.fixed.reuse_ratio) * 10_000)

    @property
    def seed_size_ratio(self) -> float:
        if self.fixed.seed_size_bytes <= 0:
            return 1.0
        return self.cdc.seed_size_bytes / self.fixed.seed_size_bytes

    def to_json(self) -> str:
        payload = {
            "source_size_bytes": self.source_size_bytes,
            "insert_offset": self.insert_offset,
            "inserted_size_bytes": self.inserted_size_bytes,
            "reuse_improvement_bps": self.reuse_improvement_bps,
            "seed_size_ratio": self.seed_size_ratio,
            "fixed": asdict(self.fixed),
            "cdc": asdict(self.cdc),
        }
        return json.dumps(payload, indent=2, sort_keys=True)


def _run_case(
    chunker: str,
    cfg: ChunkerConfig,
    base: Path,
    shifted: Path,
    workspace: Path,
    *,
    compression: str,
) -> BenchCaseResult:
    genome = workspace / f"genome-{chunker}"
    seed = workspace / f"shifted-{chunker}.hlx"

    start_prime = time.perf_counter()
    prime_genome(base, genome, chunker=chunker, cfg=cfg)
    prime_seconds = time.perf_counter() - start_prime

    start_encode = time.perf_counter()
    encode_stats = encode_file(
        in_path=shifted,
        genome_path=genome,
        out_seed_path=seed,
        chunker=chunker,
        cfg=cfg,
        learn=True,
        portable=False,
        manifest_compression=compression,
    )
    encode_seconds = time.perf_counter() - start_encode
    throughput = 0.0
    source_size = shifted.stat().st_size
    if encode_seconds > 0:
        throughput = source_size / encode_seconds / (1024 * 1024)

    return BenchCaseResult(
        chunker=chunker,
        total_chunks=encode_stats.total_chunks,
        reused_chunks=encode_stats.reused_chunks,
        new_chunks=encode_stats.new_chunks,
        seed_size_bytes=seed.stat().st_size,
        prime_seconds=prime_seconds,
        encode_seconds=encode_seconds,
        encode_throughput_mib_s=throughput,
    )


def run_shifted_dedup_benchmark(
    *,
    total_size_bytes: int = 3_200_000,
    insert_offset: int = 100_000,
    inserted: bytes = b"Z",
    random_seed: int = 42,
    chunker_cfg: ChunkerConfig | None = None,
    compression: str = "zlib",
) -> ShiftedDedupBenchmark:
    cfg = chunker_cfg or ChunkerConfig(
        min_size=4_096,
        avg_size=16_384,
        max_size=65_536,
        window_size=32,
    )
    if total_size_bytes <= 0:
        raise ValueError("total_size_bytes must be > 0")
    if not (0 <= insert_offset <= total_size_bytes):
        raise ValueError("insert_offset must be in [0, total_size_bytes]")

    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td)
        base = workspace / "base.bin"
        shifted = workspace / "shifted.bin"

        rng = random.Random(random_seed)
        original = bytes(
            rng.randrange(0, 256)
            for _ in range(total_size_bytes)
        )
        base.write_bytes(original)
        shifted.write_bytes(
            original[:insert_offset]
            + inserted
            + original[insert_offset:]
        )

        fixed = _run_case(
            "fixed", cfg, base, shifted, workspace,
            compression=compression,
        )
        cdc = _run_case(
            "cdc_buzhash", cfg, base, shifted, workspace,
            compression=compression,
        )

        return ShiftedDedupBenchmark(
            source_size_bytes=total_size_bytes,
            insert_offset=insert_offset,
            inserted_size_bytes=len(inserted),
            fixed=fixed,
            cdc=cdc,
        )


def evaluate_benchmark_gates(
    report: ShiftedDedupBenchmark,
    *,
    min_reuse_improvement_bps: int,
    max_seed_size_ratio: float,
    min_cdc_throughput_mib_s: float,
) -> list[str]:
    violations: list[str] = []
    if report.reuse_improvement_bps < min_reuse_improvement_bps:
        violations.append(
            "cdc reuse improvement below threshold: "
            f"{report.reuse_improvement_bps}bps "
            f"< {min_reuse_improvement_bps}bps"
        )
    if report.seed_size_ratio > max_seed_size_ratio:
        violations.append(
            "cdc seed size ratio above threshold: "
            f"{report.seed_size_ratio:.4f} > {max_seed_size_ratio:.4f}"
        )
    if report.cdc.encode_throughput_mib_s < min_cdc_throughput_mib_s:
        violations.append(
            "cdc throughput below threshold: "
            f"{report.cdc.encode_throughput_mib_s:.4f}MiB/s "
            f"< {min_cdc_throughput_mib_s:.4f}MiB/s"
        )
    return violations
