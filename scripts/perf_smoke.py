"""Performance regression smoke test — spec §14.2 Day 7.

Replays a 50-stock fixture through POST /api/v1/portfolio/upload 100 times
and asserts p95 latency < 5 000 ms. Run nightly via CI.

Usage::

    python scripts/perf_smoke.py [--url http://localhost:8000] [--token <jwt>]
    python scripts/perf_smoke.py --url https://api.spectraquant.in --token $TOKEN

Exit 0 = all assertions pass. Exit 1 = any assertion fails.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

import httpx

_FIXTURE_HOLDINGS = [
    {"symbol": f"S{i:04d}", "weight": round(1 / 50, 6)}
    for i in range(50)
]

_P95_LIMIT_MS = 5_000
_WARMUP = 5
_REPS = 100


def _percentile(data: list[float], pct: float) -> float:
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * pct / 100
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SpectraQuant perf smoke test")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--token", default="", help="Bearer JWT token")
    parser.add_argument("--reps", type=int, default=_REPS, help="Number of requests")
    parser.add_argument("--p95-limit-ms", type=int, default=_P95_LIMIT_MS)
    args = parser.parse_args(argv)

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    endpoint = f"{args.url.rstrip('/')}/api/v1/portfolio/upload"
    payload = {"name": "perf-smoke", "holdings": _FIXTURE_HOLDINGS}

    print(f"Smoke target: {endpoint}")
    print(f"Reps: {args.reps} (+ {_WARMUP} warmup) | p95 limit: {args.p95_limit_ms} ms")

    latencies: list[float] = []

    with httpx.Client(timeout=30.0) as client:
        # Warmup — not measured
        for _ in range(_WARMUP):
            try:
                client.post(endpoint, json=payload, headers=headers)
            except Exception:
                pass

        # Measured reps
        errors = 0
        for i in range(args.reps):
            t0 = time.perf_counter()
            try:
                resp = client.post(endpoint, json=payload, headers=headers)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if resp.status_code not in (200, 201, 400, 422):
                    errors += 1
                    print(f"  rep {i+1}: HTTP {resp.status_code} ({elapsed_ms:.0f} ms)")
                else:
                    latencies.append(elapsed_ms)
            except Exception as exc:
                errors += 1
                print(f"  rep {i+1}: ERROR {exc}")

    if not latencies:
        print("FAIL: no successful responses recorded")
        return 1

    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    mean = statistics.mean(latencies)

    print(f"\nResults ({len(latencies)} successful / {errors} errors):")
    print(f"  mean  : {mean:7.1f} ms")
    print(f"  p50   : {p50:7.1f} ms")
    print(f"  p95   : {p95:7.1f} ms  ← limit {args.p95_limit_ms} ms")
    print(f"  p99   : {p99:7.1f} ms")

    passed = True
    if p95 > args.p95_limit_ms:
        print(f"\nFAIL: p95 {p95:.0f} ms > {args.p95_limit_ms} ms limit")
        passed = False
    else:
        print(f"\nPASS: p95 {p95:.0f} ms ≤ {args.p95_limit_ms} ms limit")

    if errors > args.reps * 0.05:
        print(f"FAIL: error rate {errors}/{args.reps} exceeds 5%")
        passed = False

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
