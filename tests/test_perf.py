from __future__ import annotations

import json

import pytest

from helix.perf import (
    BenchCaseResult,
    ShiftedDedupBenchmark,
    run_shifted_dedup_benchmark,
)


def _make_case(
    chunker: str = "fixed",
    total_chunks: int = 100,
    reused_chunks: int = 50,
    seed_size_bytes: int = 1000,
) -> BenchCaseResult:
    return BenchCaseResult(
        chunker=chunker,
        total_chunks=total_chunks,
        reused_chunks=reused_chunks,
        new_chunks=total_chunks - reused_chunks,
        seed_size_bytes=seed_size_bytes,
        prime_seconds=0.1,
        encode_seconds=0.2,
        encode_throughput_mib_s=10.0,
    )


def _make_report(
    fixed_seed: int = 1000, cdc_seed: int = 800
) -> ShiftedDedupBenchmark:
    return ShiftedDedupBenchmark(
        source_size_bytes=1_000_000,
        insert_offset=100_000,
        inserted_size_bytes=1,
        fixed=_make_case("fixed", seed_size_bytes=fixed_seed),
        cdc=_make_case("cdc_buzhash", reused_chunks=75, seed_size_bytes=cdc_seed),
    )


# ---------------------------------------------------------------------------
# BenchCaseResult.reuse_ratio
# ---------------------------------------------------------------------------


def test_reuse_ratio_zero_chunks() -> None:
    r = _make_case(total_chunks=0, reused_chunks=0)
    assert r.reuse_ratio == 0.0


def test_reuse_ratio_normal() -> None:
    r = _make_case(total_chunks=100, reused_chunks=75)
    assert r.reuse_ratio == 0.75


# ---------------------------------------------------------------------------
# ShiftedDedupBenchmark.seed_size_ratio
# ---------------------------------------------------------------------------


def test_seed_size_ratio_zero_fixed() -> None:
    report = _make_report(fixed_seed=0, cdc_seed=800)
    assert report.seed_size_ratio == 1.0


def test_seed_size_ratio_normal() -> None:
    report = _make_report(fixed_seed=1000, cdc_seed=800)
    assert report.seed_size_ratio == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# ShiftedDedupBenchmark.to_json
# ---------------------------------------------------------------------------


def test_to_json_valid_output() -> None:
    report = _make_report()
    json_str = report.to_json()
    data = json.loads(json_str)

    assert data["source_size_bytes"] == 1_000_000
    assert data["insert_offset"] == 100_000
    assert "reuse_improvement_bps" in data
    assert "seed_size_ratio" in data
    assert data["fixed"]["chunker"] == "fixed"
    assert data["cdc"]["chunker"] == "cdc_buzhash"


# ---------------------------------------------------------------------------
# run_shifted_dedup_benchmark validation
# ---------------------------------------------------------------------------


def test_benchmark_invalid_total_size() -> None:
    with pytest.raises(ValueError, match="total_size_bytes must be > 0"):
        run_shifted_dedup_benchmark(total_size_bytes=0)


def test_benchmark_invalid_offset() -> None:
    with pytest.raises(ValueError, match="insert_offset must be in"):
        run_shifted_dedup_benchmark(total_size_bytes=1000, insert_offset=1001)


# ---------------------------------------------------------------------------
# run_shifted_dedup_benchmark integration (small data)
# ---------------------------------------------------------------------------


def test_benchmark_small_integration() -> None:
    report = run_shifted_dedup_benchmark(
        total_size_bytes=50_000,
        insert_offset=25_000,
    )
    assert isinstance(report, ShiftedDedupBenchmark)
    assert report.source_size_bytes == 50_000
    assert report.fixed.chunker == "fixed"
    assert report.cdc.chunker == "cdc_buzhash"
    assert report.fixed.total_chunks > 0
    assert report.cdc.total_chunks > 0
    assert report.cdc.reuse_ratio >= 0.0
