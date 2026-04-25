"""Analysis route tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from tests.conftest import TEST_USER_ID


async def test_analysis_runs_with_synthetic_factor_data(client, app) -> None:
    from src.db import get_session_factory

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2025-01-01", periods=90)

    factor_names = ["momentum", "value", "quality", "low_vol", "size", "composite"]
    factor_returns = pd.DataFrame(
        {factor: rng.normal(0.0004, 0.01, len(dates)) for factor in factor_names},
        index=dates,
    )
    portfolio_returns = (
        1.1 * factor_returns["momentum"]
        + 0.6 * factor_returns["quality"]
        - 0.3 * factor_returns["size"]
        + rng.normal(0.0, 0.002, len(dates))
    )
    prices = 100 * (1 + portfolio_returns).cumprod()

    async with get_session_factory()() as session:
        await session.execute(
            text(
                """
                INSERT INTO profiles (id, email, compliance_ack_at)
                VALUES (:id, :email, CURRENT_TIMESTAMP)
                """
            ),
            {"id": TEST_USER_ID, "email": "analysis@example.com"},
        )
        await session.execute(
            text(
                """
                INSERT INTO symbols (id, nse_symbol, company_name, isin, listed_on)
                VALUES
                    (1, 'TCS', 'Tata Consultancy Services', 'INE467B01029', '2004-08-25'),
                    (2, 'INFY', 'Infosys', 'INE009A01021', '1993-06-14')
                """
            )
        )

        for timestamp in dates:
            for factor in factor_names:
                await session.execute(
                    text(
                        """
                        INSERT INTO factor_returns (factor, return_date, daily_return)
                        VALUES (:factor, :return_date, :daily_return)
                        """
                    ),
                    {
                        "factor": factor,
                        "return_date": timestamp.date().isoformat(),
                        "daily_return": float(factor_returns.loc[timestamp, factor]),
                    },
                )

            for symbol_id in (1, 2):
                await session.execute(
                    text(
                        """
                        INSERT INTO eod_prices (symbol_id, trade_date, adj_close)
                        VALUES (:symbol_id, :trade_date, :adj_close)
                        """
                    ),
                    {
                        "symbol_id": symbol_id,
                        "trade_date": timestamp.date().isoformat(),
                        "adj_close": float(prices.loc[timestamp]),
                    },
                )

        latest_score_date = dates[-1].date().isoformat()
        score_rows = [
            (1, "momentum", 0.8),
            (1, "value", -0.2),
            (1, "quality", 0.7),
            (1, "low_vol", 0.1),
            (1, "size", -0.4),
            (1, "composite", 0.3),
            (2, "momentum", 0.4),
            (2, "value", 0.5),
            (2, "quality", 0.2),
            (2, "low_vol", -0.1),
            (2, "size", -0.6),
            (2, "composite", 0.1),
        ]
        for symbol_id, factor, z_score in score_rows:
            await session.execute(
                text(
                    """
                    INSERT INTO factor_scores (symbol_id, score_date, factor, z_score)
                    VALUES (:symbol_id, :score_date, :factor, :z_score)
                    """
                ),
                {
                    "symbol_id": symbol_id,
                    "score_date": latest_score_date,
                    "factor": factor,
                    "z_score": z_score,
                },
            )

        await session.commit()

    upload_response = await client.post(
        "/api/v1/portfolio/upload",
        json={
            "name": "Synthetic Portfolio",
            "holdings": [
                {"symbol": "TCS", "qty": 10, "avg_price": 100},
                {"symbol": "INFY", "qty": 10, "avg_price": 100},
            ],
        },
    )
    assert upload_response.status_code == 200
    portfolio_id = upload_response.json()["portfolio_id"]

    analysis_response = await client.post(
        "/api/v1/analysis/run",
        json={"portfolio_id": portfolio_id, "window_days": 90},
    )

    assert analysis_response.status_code == 200
    body = analysis_response.json()
    assert body["n_obs"] >= 60
    assert {"momentum", "quality", "size"} <= set(body["betas"])
    assert "r_squared" in body
