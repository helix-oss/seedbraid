from __future__ import annotations

from seedbraid.perf import run_shifted_dedup_benchmark


def main() -> None:
    report = run_shifted_dedup_benchmark()
    fixed = report.fixed
    cdc = report.cdc

    print("== 1-byte insertion dedup benchmark ==")
    print(
        "fixed      "
        f"reuse_ratio={fixed.reuse_ratio:.4f} "
        f"new_chunks={fixed.new_chunks} seed_size={fixed.seed_size_bytes} "
        f"throughput_mib_s={fixed.encode_throughput_mib_s:.2f}"
    )
    print(
        "cdc_buzhash "
        f"reuse_ratio={cdc.reuse_ratio:.4f} "
        f"new_chunks={cdc.new_chunks} seed_size={cdc.seed_size_bytes} "
        f"throughput_mib_s={cdc.encode_throughput_mib_s:.2f}"
    )
    print(
        "delta "
        f"reuse_improvement_bps={report.reuse_improvement_bps} "
        f"seed_size_ratio={report.seed_size_ratio:.4f}"
    )


if __name__ == "__main__":
    main()
