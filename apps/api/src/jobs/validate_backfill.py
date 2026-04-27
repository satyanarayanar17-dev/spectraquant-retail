"""Validate backfill completeness and quality per spec §14.2.5.

CLI::

    python -m apps.api.jobs.validate_backfill \\
        --start 2023-04-21 --end 2026-04-20

Checks:
  1. No gaps in factor_returns on XNSE trading days.
  2. factor_scores z_scores: mean ≈ 0, std ≈ 1 (5% tolerance).
  3. Momentum Sharpe annualised ∈ [0.2, 1.5].
  4. Cross-factor |ρ| < 0.99 for all pairs.

Exit code 0 = all PASS, exit code 1 = at least one FAIL.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate factor_returns backfill")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set", file=sys.stderr)
        return 1

    try:
        import asyncio

        import asyncpg  # type: ignore[import-untyped]
        import numpy as np
        import pandas as pd
        import pandas_market_calendars as mcal  # type: ignore[import-untyped]
    except ImportError as exc:
        print(f"ERROR: Missing dependency — {exc}", file=sys.stderr)
        return 1

    factors = ["momentum", "value", "quality", "low_vol", "size", "composite"]
    failures: list[str] = []

    async def _check() -> None:
        conn = await asyncpg.connect(db_url)
        try:
            # --- check 1: gaps in factor_returns ---
            cal = mcal.get_calendar("XNSE")
            schedule = cal.schedule(start_date=start, end_date=end)
            expected_td = set(
                t.date() for t in mcal.date_range(schedule, frequency="1D").normalize()
            )

            for factor in factors:
                rows = await conn.fetch(
                    "SELECT return_date FROM factor_returns WHERE factor=$1 "
                    "AND return_date BETWEEN $2 AND $3",
                    factor, start, end,
                )
                present = {r["return_date"] for r in rows}
                missing = expected_td - present
                if missing:
                    sample = sorted(missing)[:5]
                    failures.append(
                        f"FAIL [gaps] {factor}: {len(missing)} missing dates, "
                        f"e.g. {sample}"
                    )
                else:
                    print(f"PASS [gaps] {factor}: {len(present)} dates ✓")

            # --- check 2: z-score mean≈0, std≈1 ---
            sample_dates = await conn.fetch(
                "SELECT DISTINCT score_date FROM factor_scores "
                "WHERE score_date BETWEEN $1 AND $2 ORDER BY score_date LIMIT 30",
                start, end,
            )
            tol = 0.05
            for factor in factors:
                bad_dates = 0
                for row in sample_dates:
                    zs = await conn.fetch(
                        "SELECT z_score FROM factor_scores "
                        "WHERE factor=$1 AND score_date=$2",
                        factor, row["score_date"],
                    )
                    vals = np.array([r["z_score"] for r in zs], dtype=float)
                    if len(vals) < 10:
                        continue
                    if abs(vals.mean()) > tol or abs(vals.std() - 1.0) > tol:
                        bad_dates += 1
                if bad_dates > 0:
                    failures.append(
                        f"FAIL [z-score] {factor}: {bad_dates}/30 dates with "
                        f"|mean|>{tol} or |std-1|>{tol}"
                    )
                else:
                    print(f"PASS [z-score] {factor} ✓")

            # --- check 3: momentum Sharpe ∈ [0.2, 1.5] ---
            mom_rows = await conn.fetch(
                "SELECT daily_return FROM factor_returns "
                "WHERE factor='momentum' AND return_date BETWEEN $1 AND $2",
                start, end,
            )
            mom = np.array([r["daily_return"] for r in mom_rows], dtype=float)
            if len(mom) > 20:
                sharpe = float((mom.mean() / mom.std(ddof=1)) * math.sqrt(252))
                if 0.2 <= sharpe <= 1.5:
                    print(f"PASS [sharpe] momentum Sharpe={sharpe:.2f} ✓")
                else:
                    failures.append(
                        f"FAIL [sharpe] momentum Sharpe={sharpe:.2f} not in [0.2, 1.5]"
                    )
            else:
                print("SKIP [sharpe] insufficient data")

            # --- check 4: cross-factor |ρ| < 0.99 ---
            fr_data: dict[str, pd.Series] = {}
            for factor in factors:
                rows = await conn.fetch(
                    "SELECT return_date, daily_return FROM factor_returns "
                    "WHERE factor=$1 AND return_date BETWEEN $2 AND $3",
                    factor, start, end,
                )
                if rows:
                    fr_data[factor] = pd.Series(
                        {r["return_date"]: r["daily_return"] for r in rows}
                    )
            if len(fr_data) >= 2:
                fr_df = pd.DataFrame(fr_data).dropna()
                corr = fr_df.corr()
                bad_pairs: list[str] = []
                for i, fa in enumerate(factors):
                    for fb in factors[i + 1:]:
                        if fa in corr.columns and fb in corr.columns:
                            rho = corr.loc[fa, fb]
                            if abs(rho) >= 0.99:
                                bad_pairs.append(f"({fa},{fb})={rho:.3f}")
                if bad_pairs:
                    failures.append(f"FAIL [corr] |ρ|≥0.99: {bad_pairs}")
                else:
                    print("PASS [corr] all factor pairs |ρ|<0.99 ✓")
        finally:
            await conn.close()

    asyncio.run(_check())

    if failures:
        print("\n--- FAILURES ---")
        for f in failures:
            print(f)
        return 1

    print("\nAll checks PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
