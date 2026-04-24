"""Pydantic v2 data models for price and fundamental inputs."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class PriceFrame(BaseModel):
    """Single row of adjusted-close price data."""

    symbol_id: str
    trade_date: date
    adj_close: float

    @field_validator("adj_close")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"adj_close must be positive, got {v}")
        return v


class FundamentalsFrame(BaseModel):
    """Single row of fundamental data for one symbol and reporting period."""

    symbol_id: str
    period_end: date
    market_cap: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None
    roe: float | None = None
    roce: float | None = None
    debt_to_equity: float | None = None
    eps_ttm: float | None = None
