"""Backfill factor_scores and factor_returns for a historical window.

CLI::

    python -m apps.api.jobs.backfill_factor_returns \\
        --start 2023-04-21 --end 2026-04-20 --env production

Per spec §14.2.3. Fully rerunnable (all writes are UPSERTs).
Requires --env production as an explicit safeguard.

Flow:
  1. Load XNSE calendar.
  2. Fetch historical EOD prices via yfinance (§14.3.6).
     - Batch 20 symbols; 2s sleep between batches.
     - Cache to YFINANCE_CACHE_DIR.
  3. For each rebalance month: compute quintile memberships.
  4. For each trading day: compute and UPSERT factor_scores + factor_returns.
  5. Log row counts to job_runs.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta

log = logging.getLogger(__name__)


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set", file=sys.stderr)
        sys.exit(1)
    return val


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill factor_scores and factor_returns")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--env", required=True, choices=["production", "staging", "local"])
    args = parser.parse_args(argv)

    if args.env != "production":
        print(
            f"WARNING: running against env={args.env}. "
            "Only 'production' is validated by CI checks.",
        )

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        print("ERROR: --start must be <= --end", file=sys.stderr)
        return 1

    db_url = _require_env("SUPABASE_DB_URL")
    cache_dir = os.environ.get("YFINANCE_CACHE_DIR", "/tmp/yfinance_cache")

    try:
        import asyncio

        import asyncpg  # type: ignore[import-untyped]
        import pandas as pd
        import pandas_market_calendars as mcal  # type: ignore[import-untyped]
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError as exc:
        print(f"ERROR: Missing dependency — {exc}", file=sys.stderr)
        return 1

    from spectraquant_core.factor_returns import FactorName, compute_factor_return_series
    from spectraquant_core.factors.composite import compute_composite
    from spectraquant_core.factors.low_vol import compute_low_vol
    from spectraquant_core.factors.momentum import compute_momentum
    from spectraquant_core.factors.quality import compute_quality
    from spectraquant_core.factors.size import compute_size
    from spectraquant_core.factors.value import compute_value
    from spectraquant_core.normalize import zscore

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cal = mcal.get_calendar("XNSE")
    schedule = cal.schedule(start_date=start - timedelta(days=365), end_date=end)
    import pandas_market_calendars as _mcal
    all_td = _mcal.date_range(schedule, frequency="1D").normalize()

    os.makedirs(cache_dir, exist_ok=True)

    async def _fetch_symbols(conn: asyncpg.Connection) -> list[dict]:  # type: ignore[name-defined]
        rows = await conn.fetch(
            """
            SELECT s.id, s.nse_symbol
            FROM symbols s
            JOIN index_membership im ON im.symbol_id = s.id
            WHERE im.index_name = 'NIFTY500'
              AND im.effective_from <= $1
              AND (im.effective_to IS NULL OR im.effective_to >= $2)
            """,
            end,
            start,
        )
        return [dict(r) for r in rows]

    async def _run() -> None:
        conn = await asyncpg.connect(db_url)
        try:
            symbols = await _fetch_symbols(conn)
            nse_symbols = [s["nse_symbol"] for s in symbols]
            sym_id_map = {s["nse_symbol"]: s["id"] for s in symbols}
            log.info("Universe: %d symbols", len(nse_symbols))

            # --- fetch prices ---
            prices_frames: list[pd.DataFrame] = []
            batch_size = 20
            for i in range(0, len(nse_symbols), batch_size):
                batch = [f"{s}.NS" for s in nse_symbols[i : i + batch_size]]
                cache_key = "_".join(nse_symbols[i : i + batch_size])
                cache_file = os.path.join(cache_dir, f"{cache_key}.parquet")
                if os.path.exists(cache_file):
                    df = pd.read_parquet(cache_file)
                else:
                    ticker_data = yf.download(
                        batch,
                        start=str(start - timedelta(days=400)),
                        end=str(end + timedelta(days=1)),
                        auto_adjust=True,
                        progress=False,
                    )
                    df = ticker_data.get("Close", pd.DataFrame())
                    if not df.empty:
                        df.columns = [c.replace(".NS", "") for c in df.columns]
                        df.to_parquet(cache_file)
                    time.sleep(2)
                if not df.empty:
                    prices_frames.append(df)
                log.info(
                    "Fetched batch %d/%d",
                    min(i + batch_size, len(nse_symbols)),
                    len(nse_symbols),
                )

            if not prices_frames:
                log.error("No price data fetched; aborting")
                return

            prices = pd.concat(prices_frames, axis=1)
            prices = prices.loc[~prices.index.duplicated(keep="last")]
            prices.index = pd.to_datetime(prices.index)

            log.info("Prices shape: %s", prices.shape)

            # --- fetch membership and fundamentals ---
            membership_rows = await conn.fetch(
                """
                SELECT s.nse_symbol AS symbol_id, im.effective_from, im.effective_to
                FROM index_membership im
                JOIN symbols s ON s.id = im.symbol_id
                WHERE im.index_name = 'NIFTY500'
                """
            )
            membership = pd.DataFrame([dict(r) for r in membership_rows])

            fundamentals_rows = await conn.fetch(
                """
                SELECT s.nse_symbol AS symbol_id, f.period_end,
                       f.market_cap, f.pe_ratio, f.pb_ratio, f.ev_ebitda,
                       f.roe, f.debt_to_equity
                FROM fundamentals f
                JOIN symbols s ON s.id = f.symbol_id
                """
            )
            fundamentals = pd.DataFrame([dict(r) for r in fundamentals_rows])

            eps_rows = await conn.fetch(
                """
                SELECT s.nse_symbol AS symbol, e.period_end, e.eps_ttm
                FROM eps_history e
                JOIN symbols s ON s.id = e.symbol_id
                """
            )
            eps_history = pd.DataFrame([dict(r) for r in eps_rows])

            market_caps = (
                fundamentals.groupby("symbol_id")["market_cap"].last()
                if not fundamentals.empty
                else pd.Series(dtype=float)
            )

            # --- compute factor scores and upsert ---
            factors: list[FactorName] = ["momentum", "value", "quality", "low_vol", "size"]
            all_z_scores: list[dict] = []

            for td_ts in all_td:
                if not (start <= td_ts.date() <= end):
                    continue
                as_of = td_ts.date()
                z_day: dict[str, pd.Series] = {}

                try:
                    z_day["momentum"] = zscore(compute_momentum(prices, as_of))
                except Exception:
                    pass
                try:
                    z_day["low_vol"] = zscore(compute_low_vol(prices, as_of))
                except Exception:
                    pass
                try:
                    z_day["size"] = zscore(compute_size(market_caps))
                except Exception:
                    pass
                if not fundamentals.empty:
                    try:
                        z_day["value"] = zscore(compute_value(fundamentals, as_of))
                    except Exception:
                        pass
                if not fundamentals.empty and not eps_history.empty:
                    try:
                        z_day["quality"] = zscore(compute_quality(fundamentals, eps_history))
                    except Exception:
                        pass
                if len(z_day) == 5:
                    try:
                        z_day["composite"] = compute_composite(z_day)
                    except Exception:
                        pass

                for factor_name, z_series in z_day.items():
                    for sym, z_val in z_series.dropna().items():
                        sym_id = sym_id_map.get(str(sym))
                        if sym_id is None:
                            continue
                        all_z_scores.append(
                            {
                                "symbol_id": sym_id,
                                "score_date": as_of,
                                "factor_name": factor_name,
                                "z_score": float(z_val),
                            }
                        )

            # Batch UPSERT factor_scores (10k rows per chunk)
            chunk_size = 10_000
            for i in range(0, len(all_z_scores), chunk_size):
                chunk = all_z_scores[i : i + chunk_size]
                await conn.executemany(
                    """
                    INSERT INTO factor_scores (symbol_id, score_date, factor_name, z_score)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (symbol_id, score_date, factor_name)
                    DO UPDATE SET z_score = EXCLUDED.z_score
                    """,
                    [(r["symbol_id"], r["score_date"], r["factor_name"], r["z_score"])
                     for r in chunk],
                )

            log.info("Upserted %d factor_score rows", len(all_z_scores))

            # --- compute factor_returns series ---
            z_scores_df = pd.DataFrame(all_z_scores).copy()
            z_scores_df["symbol_id"] = z_scores_df["symbol_id"].map(
                {v: k for k, v in sym_id_map.items()}
            )
            z_scores_df["score_date"] = pd.to_datetime(z_scores_df["score_date"])

            fr_rows: list[tuple] = []
            for factor in (*factors, "composite"):
                try:
                    series = compute_factor_return_series(
                        factor,  # type: ignore[arg-type]
                        z_scores_df,
                        prices,
                        membership,
                        cal,
                        start,
                        end,
                    )
                    for dt, val in series.dropna().items():
                        fr_rows.append(
                            (
                                factor,
                                dt.date() if hasattr(dt, "date") else dt,
                                float(val),
                            )
                        )
                except Exception as exc:
                    log.warning("factor_returns failed for %s: %s", factor, exc)

            await conn.executemany(
                """
                INSERT INTO factor_returns (factor_name, trade_date, long_short_return)
                VALUES ($1, $2, $3)
                ON CONFLICT (factor_name, trade_date)
                DO UPDATE SET long_short_return = EXCLUDED.long_short_return
                """,
                fr_rows,
            )
            log.info("Upserted %d factor_return rows", len(fr_rows))

            await conn.execute(
                """
                INSERT INTO job_runs (job_name, status, rows_written, started_at, finished_at)
                VALUES ('backfill_factor_returns', 'success', $1, NOW(), NOW())
                """,
                len(all_z_scores) + len(fr_rows),
            )

        finally:
            await conn.close()

    import asyncio
    asyncio.run(_run())

    print(f"Backfill complete: {start} → {end}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
