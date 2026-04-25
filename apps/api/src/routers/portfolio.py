"""Portfolio upload and retrieval routes."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from spectraquant_core.errors import ZeroWeightPortfolioError
from spectraquant_core.portfolio import Holding, normalize_weights
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.config import get_settings
from src.db import DbSession

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


class PortfolioUploadRequest(BaseModel):
    """Upload payload for a new portfolio."""

    holdings: list[Holding] = Field(min_length=1)
    name: str = Field(default="Portfolio", min_length=1, max_length=120)


class PortfolioUploadResponse(BaseModel):
    """Upload response payload."""

    portfolio_id: UUID


class PortfolioResponse(BaseModel):
    """Decrypted portfolio payload."""

    id: UUID
    name: str
    holdings: list[dict[str, Any]]


def _serialise_holdings(holdings: list[Holding]) -> str:
    payload = [
        holding.model_dump(mode="json", exclude_none=True)
        for holding in holdings
    ]
    return json.dumps(payload, separators=(",", ":"))


def _content_hash(holdings: list[Holding]) -> str:
    canonical = sorted(
        (
            {
                "symbol": holding.symbol.strip().upper(),
                **holding.model_dump(exclude={"symbol"}, exclude_none=True),
            }
            for holding in holdings
        ),
        key=lambda row: row["symbol"],
    )
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _total_value(holdings: list[Holding]) -> float | None:
    if any(holding.qty is None or holding.avg_price is None for holding in holdings):
        return None
    return float(
        sum(
            (holding.qty or 0.0) * (holding.avg_price or 0.0)
            for holding in holdings
        )
    )


def _decode_holdings(raw_value: Any) -> list[dict[str, Any]]:
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
    return loaded


async def _validate_symbols(session: AsyncSession, holdings: list[Holding]) -> None:
    requested_symbols = sorted({holding.symbol.strip().upper() for holding in holdings})
    if not requested_symbols:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No symbols provided",
        )

    symbol_query = text(
        "SELECT nse_symbol FROM symbols WHERE nse_symbol IN :symbols"
    ).bindparams(bindparam("symbols", expanding=True))
    result = await session.execute(symbol_query, {"symbols": requested_symbols})
    existing = {row[0] for row in result.all()}
    missing = sorted(set(requested_symbols) - existing)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "unknown_symbols", "symbols": missing},
        )


@router.post("/upload", response_model=PortfolioUploadResponse)
async def upload_portfolio(
    payload: PortfolioUploadRequest,
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> PortfolioUploadResponse:
    """Encrypt and persist a user portfolio."""

    normalized_holdings = [
        holding.model_copy(update={"symbol": holding.symbol.strip().upper()})
        for holding in payload.holdings
    ]

    try:
        normalize_weights(normalized_holdings)
    except ZeroWeightPortfolioError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await _validate_symbols(session, normalized_holdings)

    settings = get_settings()
    portfolio_id = uuid4()
    insert_query = text(
        """
        INSERT INTO portfolios (
            id,
            user_id,
            name,
            holdings_enc,
            num_holdings,
            total_value_inr,
            content_hash
        )
        VALUES (
            :portfolio_id,
            :user_id,
            :name,
            pgp_sym_encrypt(:holdings_json, :enc_key),
            :num_holdings,
            :total_value_inr,
            :content_hash
        )
        RETURNING id
        """
    )

    result = await session.execute(
        insert_query,
        {
            "portfolio_id": str(portfolio_id),
            "user_id": current_user["sub"],
            "name": payload.name.strip(),
            "holdings_json": _serialise_holdings(normalized_holdings),
            "enc_key": settings.holdings_enc_key,
            "num_holdings": len(normalized_holdings),
            "total_value_inr": _total_value(normalized_holdings),
            "content_hash": _content_hash(normalized_holdings),
        },
    )
    await session.commit()

    _ = result.scalar_one()
    return PortfolioUploadResponse(portfolio_id=portfolio_id)


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> PortfolioResponse:
    """Return the authenticated user's decrypted portfolio."""

    settings = get_settings()
    query = text(
        """
        SELECT
            id,
            name,
            pgp_sym_decrypt(holdings_enc, :enc_key) AS holdings_json
        FROM portfolios
        WHERE id = :portfolio_id
          AND user_id = :user_id
          AND deleted_at IS NULL
        """
    )

    result = await session.execute(
        query,
        {
            "portfolio_id": str(portfolio_id),
            "user_id": current_user["sub"],
            "enc_key": settings.holdings_enc_key,
        },
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    return PortfolioResponse(
        id=row["id"],
        name=row["name"],
        holdings=_decode_holdings(row["holdings_json"]),
    )
