"""Portfolio analysis routes."""

from __future__ import annotations

import json
import time
from typing import Any, cast
from uuid import UUID

import pandas as pd
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from spectraquant_core.attribution import compute_attribution
from spectraquant_core.errors import InsufficientDataError, ZeroWeightPortfolioError
from spectraquant_core.portfolio import Holding, compute_exposures, normalize_weights
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.config import get_settings
from src.db import DbSession

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
logger = structlog.get_logger(__name__)


def _sql_date(value: pd.Timestamp) -> str:
    return value.date().isoformat()


class AnalysisRunRequest(BaseModel):
    """Run-analysis request payload."""

    portfolio_id: UUID
    window_days: int = Field(default=252, ge=60, le=756)


def _decode_holdings(raw_value: Any) -> list[Holding]:
    if isinstance(raw_value, bytes):
        text_value = raw_value.decode("utf-8")
    else:
        text_value = str(raw_value)
    loaded = json.loads(text_value)
    if not isinstance(loaded, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid holdings payload",
        )
    return [Holding.model_validate(item) for item in loaded]


async def _load_holdings(
    session: AsyncSession,
    portfolio_id: UUID,
    user_id: str,
) -> list[Holding]:
    settings = get_settings()
    portfolio_query = text(
        """
        SELECT pgp_sym_decrypt(holdings_enc, :enc_key) AS holdings_json
        FROM portfolios
        WHERE id = :portfolio_id
          AND user_id = :user_id
          AND deleted_at IS NULL
        """
    )
    result = await session.execute(
        portfolio_query,
        {
            "portfolio_id": str(portfolio_id),
            "user_id": user_id,
            "enc_key": settings.holdings_enc_key,
        },
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return _decode_holdings(row["holdings_json"])


async def _symbol_id_map(session: AsyncSession, symbols: list[str]) -> dict[str, int]:
    query = text(
        """
        SELECT id, nse_symbol
        FROM symbols
        WHERE nse_symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    result = await session.execute(query, {"symbols": symbols})
    return {row.nse_symbol: row.id for row in result.mappings().all()}


async def _load_factor_returns(session: AsyncSession, days: int) -> pd.DataFrame:
    query = text(
        """
        WITH recent_dates AS (
            SELECT DISTINCT return_date
            FROM factor_returns
            ORDER BY return_date DESC
            LIMIT :days
        )
        SELECT factor, return_date, daily_return
        FROM factor_returns
        WHERE return_date IN (SELECT return_date FROM recent_dates)
        ORDER BY return_date ASC, factor ASC
        """
    )
    result = await session.execute(query, {"days": days})
    rows = result.mappings().all()
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["return_date"] = pd.to_datetime(frame["return_date"])
    pivoted = frame.pivot(index="return_date", columns="factor", values="daily_return")
    return pivoted.sort_index()


async def _load_factor_scores(
    session: AsyncSession,
    symbols: list[str],
) -> dict[str, pd.Series]:
    latest_score_query = text("SELECT MAX(score_date) AS score_date FROM factor_scores")
    latest_score_row = (await session.execute(latest_score_query)).mappings().first()
    latest_score = latest_score_row["score_date"] if latest_score_row is not None else None
    if latest_score is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No factor scores available",
        )

    query = text(
        """
        SELECT s.nse_symbol, fs.factor, fs.z_score
        FROM factor_scores fs
        JOIN symbols s ON s.id = fs.symbol_id
        WHERE fs.score_date = :score_date
          AND s.nse_symbol IN :symbols
        ORDER BY fs.factor ASC, s.nse_symbol ASC
        """
    ).bindparams(bindparam("symbols", expanding=True))
    result = await session.execute(query, {"score_date": latest_score, "symbols": symbols})
    rows = result.mappings().all()
    if not rows:
        return {}

    frame = pd.DataFrame(rows)
    exposures: dict[str, pd.Series] = {}
    for factor_name, factor_frame in frame.groupby("factor"):
        exposures[str(factor_name)] = factor_frame.set_index("nse_symbol")["z_score"].astype(float)
    return exposures


async def _load_price_history(
    session: AsyncSession,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    query = text(
        """
        SELECT s.nse_symbol, e.trade_date, e.adj_close
        FROM eod_prices e
        JOIN symbols s ON s.id = e.symbol_id
        WHERE s.nse_symbol IN :symbols
          AND e.trade_date BETWEEN :start_date AND :end_date
        ORDER BY e.trade_date ASC, s.nse_symbol ASC
        """
    ).bindparams(bindparam("symbols", expanding=True))
    result = await session.execute(
        query,
        {
            "symbols": symbols,
            "start_date": _sql_date(start_date),
            "end_date": _sql_date(end_date),
        },
    )
    rows = result.mappings().all()
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    prices = frame.pivot(index="trade_date", columns="nse_symbol", values="adj_close")
    return prices.sort_index()


@router.post("/run")
async def run_analysis(
    payload: AnalysisRunRequest,
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Run exposure + attribution analysis for a portfolio."""

    started_at = time.monotonic()
    holdings = await _load_holdings(session, payload.portfolio_id, current_user["sub"])

    try:
        weights = normalize_weights(holdings)
    except ZeroWeightPortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    symbols = [str(symbol).strip().upper() for symbol in weights.index.tolist()]
    factor_returns = await _load_factor_returns(session, payload.window_days)
    if factor_returns.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No factor returns available",
        )

    factor_scores = await _load_factor_scores(session, symbols)
    exposures = compute_exposures(weights, factor_scores)

    price_history = await _load_price_history(
        session,
        symbols=symbols,
        start_date=factor_returns.index.min(),
        end_date=factor_returns.index.max(),
    )
    if price_history.empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No price history available",
        )

    aligned_weights = weights.reindex(price_history.columns).fillna(0.0)
    portfolio_returns = (
        price_history.pct_change()
        .reindex(factor_returns.index)
        .mul(aligned_weights, axis=1)
        .sum(axis=1, min_count=1)
    )

    combined = pd.concat([portfolio_returns.rename("_ret"), factor_returns], axis=1).dropna()
    actual_obs = len(combined)
    if actual_obs < 60:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "insufficient_history",
                "message": (
                    "Attribution requires at least 60 trading days of portfolio history. "
                    f"This portfolio has {actual_obs} days."
                ),
                "min_obs": 60,
                "actual_obs": actual_obs,
            },
        )

    try:
        result = compute_attribution(portfolio_returns, factor_returns)
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "insufficient_history",
                "message": str(exc),
                "min_obs": 60,
                "actual_obs": actual_obs,
            },
        ) from exc

    elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
    logger.info(
        "portfolio_analysis_completed",
        portfolio_id=str(payload.portfolio_id),
        user_id=current_user["sub"],
        window_days=payload.window_days,
        elapsed_ms=elapsed_ms,
        n_obs=result.n_obs,
        exposures=exposures,
    )

    return cast(dict[str, Any], result.model_dump(mode="json"))
