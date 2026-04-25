"""Seed index_membership from NSE NIFTY500 constituent changes Excel.

CLI::

    python -m apps.api.jobs.seed_index_membership <path_to_xlsx>

Parses the "NIFTY500 Constituent Changes" Excel published by NSE.
Resolves symbols against symbols.nse_symbol. Inserts
(index_name, symbol_id, effective_from, effective_to) rows.
ON CONFLICT DO NOTHING — safe to re-run.

Must run after seed_symbols.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed index_membership from NIFTY500 constituent changes XLSX"
    )
    parser.add_argument("xlsx_path", help="Path to NIFTY500 constituent changes Excel file")
    args = parser.parse_args(argv)

    xlsx_path = Path(args.xlsx_path)
    if not xlsx_path.exists():
        print(f"ERROR: File not found: {xlsx_path}", file=sys.stderr)
        return 1

    try:
        import asyncio

        import asyncpg  # type: ignore[import-untyped]
        import openpyxl  # type: ignore[import-untyped]
    except ImportError as exc:
        print(f"ERROR: Missing dependency — {exc}. Run: uv pip install asyncpg openpyxl",
              file=sys.stderr)
        return 1

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set", file=sys.stderr)
        return 1

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    headers: list[str] = []
    raw_rows: list[dict[str, object]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c).strip() if c else "" for c in row]
            continue
        record = dict(zip(headers, row))
        raw_rows.append(record)
    wb.close()

    def _to_date(val: object) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        from datetime import datetime
        for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(val).strip(), fmt).date()
            except ValueError:
                continue
        return None

    membership_rows: list[tuple[str, str, date | None, date | None]] = []
    for r in raw_rows:
        sym_col = next((v for k, v in r.items() if "symbol" in k.lower()), None)
        from_col = next((v for k, v in r.items() if "from" in k.lower() or "includ" in k.lower()), None)
        to_col = next((v for k, v in r.items() if "to" in k.lower() or "exclud" in k.lower()), None)
        if not sym_col:
            continue
        membership_rows.append(
            (
                "NIFTY500",
                str(sym_col).strip(),
                _to_date(from_col),
                _to_date(to_col),
            )
        )

    if not membership_rows:
        print("ERROR: No membership rows parsed — check Excel column names", file=sys.stderr)
        return 1

    async def _insert() -> int:
        conn = await asyncpg.connect(db_url)
        count = 0
        try:
            for index_name, nse_sym, eff_from, eff_to in membership_rows:
                symbol_id = await conn.fetchval(
                    "SELECT id FROM symbols WHERE nse_symbol = $1", nse_sym
                )
                if symbol_id is None:
                    continue
                await conn.execute(
                    """
                    INSERT INTO index_membership
                        (index_name, symbol_id, effective_from, effective_to)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    index_name,
                    symbol_id,
                    eff_from,
                    eff_to,
                )
                count += 1
        finally:
            await conn.close()
        return count

    inserted = asyncio.run(_insert())
    print(f"Done. inserted={inserted} skipped={len(membership_rows) - inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
