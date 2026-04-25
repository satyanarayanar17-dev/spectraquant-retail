"""Factor data routes."""

from __future__ import annotations

from enum import StrEnum

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.db import DbSession

router = APIRouter(prefix="/api/v1/factors", tags=["factors"])


class FactorName(StrEnum):
    momentum = "momentum"
    value = "value"
    quality = "quality"
    low_vol = "low_vol"
    size = "size"
    composite = "composite"


@router.get("/returns")
async def get_factor_returns(
    factor: FactorName,
    _current_user: CurrentUser,
    days: int = Query(default=252, ge=1, le=756),
    session: AsyncSession = DbSession,
) -> dict[str, object]:
    """Return a window of factor return values."""

    query = text(
        """
        SELECT return_date, daily_return
        FROM factor_returns
        WHERE factor = :factor
        ORDER BY return_date DESC
        LIMIT :days
        """
    )
    result = await session.execute(query, {"factor": factor.value, "days": days})
    rows = list(reversed(result.mappings().all()))

    return {
        "factor": factor.value,
        "dates": [row["return_date"].isoformat() for row in rows],
        "values": [float(row["daily_return"]) for row in rows],
    }


@router.get("/scores/latest")
async def get_latest_scores(
    _current_user: CurrentUser,
    symbols: str = Query(..., min_length=1),
    session: AsyncSession = DbSession,
) -> dict[str, object]:
    """Return the latest z-scores for a requested symbol set."""

    requested_symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if not requested_symbols:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No symbols requested",
        )

    latest_score_query = text("SELECT MAX(score_date) AS score_date FROM factor_scores")
    latest_score_row = (await session.execute(latest_score_query)).mappings().first()
    score_date = latest_score_row["score_date"] if latest_score_row is not None else None
    if score_date is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No factor scores available",
        )

    query = text(
        """
        SELECT s.nse_symbol, fs.factor, fs.z_score
        FROM factor_scores fs
        JOIN symbols s ON s.id = fs.symbol_id
        WHERE fs.score_date = :score_date
          AND s.nse_symbol IN :symbols
        ORDER BY s.nse_symbol ASC, fs.factor ASC
        """
    ).bindparams(bindparam("symbols", expanding=True))
    result = await session.execute(
        query,
        {
            "score_date": score_date,
            "symbols": requested_symbols,
        },
    )

    scores: dict[str, dict[str, float]] = {
        symbol: {} for symbol in requested_symbols
    }
    for row in result.mappings().all():
        scores[str(row["nse_symbol"])][str(row["factor"])] = float(row["z_score"])

    return {
        "score_date": score_date.isoformat(),
        "scores": scores,
    }
