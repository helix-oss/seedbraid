from __future__ import annotations

import argparse
from pathlib import Path

from helix.perf import evaluate_benchmark_gates, run_shifted_dedup_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run shifted dedup benchmark and enforce regression gates."
        ),
    )
    parser.add_argument("--total-size-bytes", type=int, default=3_200_000)
    parser.add_argument("--insert-offset", type=int, default=100_000)
    parser.add_argument("--min-reuse-improvement-bps", type=int, default=1)
    parser.add_argument("--max-seed-size-ratio", type=float, default=1.20)
    parser.add_argument("--min-cdc-throughput-mib-s", type=float, default=0.10)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_shifted_dedup_benchmark(
        total_size_bytes=args.total_size_bytes,
        insert_offset=args.insert_offset,
    )
    violations = evaluate_benchmark_gates(
        report,
        min_reuse_improvement_bps=args.min_reuse_improvement_bps,
        max_seed_size_ratio=args.max_seed_size_ratio,
        min_cdc_throughput_mib_s=args.min_cdc_throughput_mib_s,
    )

    print("== benchmark gate summary ==")
    print(
        f"reuse_improvement_bps={report.reuse_improvement_bps} "
        f"seed_size_ratio={report.seed_size_ratio:.4f} "
        f"cdc_throughput_mib_s={report.cdc.encode_throughput_mib_s:.4f}"
    )

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(report.to_json() + "\n")
        print(f"json_report={args.json_out}")

    if violations:
        print("benchmark_gate=FAIL")
        for issue in violations:
            print(f"- {issue}")
        return 1

    print("benchmark_gate=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
