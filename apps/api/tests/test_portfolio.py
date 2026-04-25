"""Portfolio route tests."""

from __future__ import annotations

from sqlalchemy import text

from tests.conftest import TEST_USER_ID


async def test_upload_round_trip_returns_original_holdings(client, app) -> None:
    from src.db import get_session_factory

    async with get_session_factory()() as session:
        await session.execute(
            text(
                """
                INSERT INTO profiles (id, email, compliance_ack_at)
                VALUES (:id, :email, CURRENT_TIMESTAMP)
                """
            ),
            {"id": TEST_USER_ID, "email": "test@example.com"},
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
        await session.commit()

    payload = {
        "name": "Core Holdings",
        "holdings": [
            {"symbol": "TCS", "qty": 10, "avg_price": 100},
            {"symbol": "INFY", "qty": 5, "avg_price": 200},
        ],
    }

    upload_response = await client.post("/api/v1/portfolio/upload", json=payload)
    assert upload_response.status_code == 200
    portfolio_id = upload_response.json()["portfolio_id"]

    fetch_response = await client.get(f"/api/v1/portfolio/{portfolio_id}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["holdings"] == payload["holdings"]
