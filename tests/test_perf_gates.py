from __future__ import annotations

from helix.perf import (
    BenchCaseResult,
    ShiftedDedupBenchmark,
    evaluate_benchmark_gates,
)


def _report(
    *,
    reuse_improvement_bps: int,
    seed_size_ratio: float,
    throughput: float,
) -> ShiftedDedupBenchmark:
    fixed = BenchCaseResult(
        chunker="fixed",
        total_chunks=100,
        reused_chunks=50,
        new_chunks=50,
        seed_size_bytes=1000,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=throughput,
    )
    cdc_reuse = fixed.reused_chunks + int(reuse_improvement_bps / 100)
    cdc_seed_size = int(fixed.seed_size_bytes * seed_size_ratio)
    cdc = BenchCaseResult(
        chunker="cdc_buzhash",
        total_chunks=100,
        reused_chunks=cdc_reuse,
        new_chunks=100 - cdc_reuse,
        seed_size_bytes=cdc_seed_size,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=throughput,
    )
    return ShiftedDedupBenchmark(
        source_size_bytes=1_000_000,
        insert_offset=1000,
        inserted_size_bytes=1,
        fixed=fixed,
        cdc=cdc,
    )


def test_evaluate_benchmark_gates_passes() -> None:
    report = _report(
        reuse_improvement_bps=100, seed_size_ratio=1.0, throughput=10.0
    )
    violations = evaluate_benchmark_gates(
        report,
        min_reuse_improvement_bps=1,
        max_seed_size_ratio=1.2,
        min_cdc_throughput_mib_s=0.1,
    )
    assert violations == []


def test_evaluate_benchmark_gates_detects_regressions() -> None:
    report = _report(
        reuse_improvement_bps=0, seed_size_ratio=1.5, throughput=0.01
    )
    violations = evaluate_benchmark_gates(
        report,
        min_reuse_improvement_bps=10,
        max_seed_size_ratio=1.2,
        min_cdc_throughput_mib_s=0.1,
    )
    assert len(violations) == 3
