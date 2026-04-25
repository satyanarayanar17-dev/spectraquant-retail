"""Seed the symbols table from NSE EQUITY_L.csv.

CLI::

    python -m apps.api.jobs.seed_symbols <path_to_equity_csv>

Input: NSE equity master CSV (EQUITY_L.csv from NSE India → Market Data →
Equity downloads). Columns: SYMBOL, NAME OF COMPANY, ISIN NUMBER,
DATE OF LISTING (DD-MMM-YYYY).

UPSERT on nse_symbol: updates isin, company_name, listed_on if changed.
Must run before seed_index_membership.py.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path


def _parse_listed_on(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed symbols table from NSE EQUITY_L.csv")
    parser.add_argument("csv_path", help="Path to EQUITY_L.csv")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}", file=sys.stderr)
        return 1

    try:
        import asyncpg  # type: ignore[import-untyped]
        import asyncio
    except ImportError:
        print("ERROR: asyncpg not installed. Run: uv pip install asyncpg", file=sys.stderr)
        return 1

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set", file=sys.stderr)
        return 1

    rows: list[dict[str, object]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            nse_symbol = row.get("SYMBOL", "").strip()
            if not nse_symbol:
                continue
            rows.append(
                {
                    "nse_symbol": nse_symbol,
                    "company_name": row.get("NAME OF COMPANY", "").strip(),
                    "isin": row.get("ISIN NUMBER", "").strip() or None,
                    "listed_on": _parse_listed_on(row.get("DATE OF LISTING", "")),
                }
            )

    if not rows:
        print("ERROR: No rows parsed — check CSV column names", file=sys.stderr)
        return 1

    async def _upsert() -> tuple[int, int]:
        conn = await asyncpg.connect(db_url)
        inserted = updated = 0
        try:
            for r in rows:
                result = await conn.fetchrow(
                    """
                    INSERT INTO symbols (nse_symbol, company_name, isin, listed_on)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (nse_symbol) DO UPDATE
                      SET company_name = EXCLUDED.company_name,
                          isin = EXCLUDED.isin,
                          listed_on = EXCLUDED.listed_on
                    RETURNING (xmax = 0) AS was_inserted
                    """,
                    r["nse_symbol"],
                    r["company_name"],
                    r["isin"],
                    r["listed_on"],
                )
                if result and result["was_inserted"]:
                    inserted += 1
                else:
                    updated += 1
        finally:
            await conn.close()
        return inserted, updated

    inserted, updated = asyncio.run(_upsert())
    skipped = len(rows) - inserted - updated
    print(f"Done. inserted={inserted} updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
