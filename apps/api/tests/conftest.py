"""Shared test fixtures for the API app."""

# ruff: noqa: E402

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
CORE_SRC = REPO_ROOT / "packages" / "spectraquant-core" / "src"

for candidate in (str(CORE_SRC), str(API_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_DB_URL", f"sqlite+aiosqlite:///{API_ROOT / 'test-bootstrap.db'}")
os.environ.setdefault("HOLDINGS_ENC_KEY", "test-secret")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

from src.auth import clear_jwks_cache, verify_jwt_dependency
from src.config import clear_settings_cache
from src.db import dispose_engine
from src.main import create_app

TEST_USER_ID = str(uuid4())


def _create_schema(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE profiles (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            compliance_ack_at TEXT
        );

        CREATE TABLE symbols (
            id INTEGER PRIMARY KEY,
            nse_symbol TEXT NOT NULL UNIQUE,
            company_name TEXT NOT NULL,
            isin TEXT NOT NULL UNIQUE,
            listed_on TEXT
        );

        CREATE TABLE portfolios (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            user_id TEXT NOT NULL REFERENCES profiles(id),
            name TEXT NOT NULL,
            holdings_enc BLOB NOT NULL,
            num_holdings INTEGER NOT NULL,
            total_value_inr REAL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        );

        CREATE TABLE factor_scores (
            symbol_id INTEGER NOT NULL REFERENCES symbols(id),
            score_date TEXT NOT NULL,
            factor TEXT NOT NULL,
            z_score REAL NOT NULL,
            PRIMARY KEY (symbol_id, score_date, factor)
        );

        CREATE TABLE factor_returns (
            factor TEXT NOT NULL,
            return_date TEXT NOT NULL,
            daily_return REAL NOT NULL,
            PRIMARY KEY (factor, return_date)
        );

        CREATE TABLE eod_prices (
            symbol_id INTEGER NOT NULL REFERENCES symbols(id),
            trade_date TEXT NOT NULL,
            adj_close REAL NOT NULL,
            PRIMARY KEY (symbol_id, trade_date)
        );
        """
    )
    connection.commit()
    connection.close()


@pytest_asyncio.fixture()
async def app(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "api-test.db"
    _create_schema(db_path)

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_DB_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("HOLDINGS_ENC_KEY", "test-secret")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")

    clear_settings_cache()
    clear_jwks_cache()
    await dispose_engine()

    application = create_app()

    async def _current_user_override() -> dict[str, str]:
        return {"sub": TEST_USER_ID, "aud": "authenticated"}

    application.dependency_overrides[verify_jwt_dependency] = _current_user_override
    yield application
    application.dependency_overrides.clear()
    await dispose_engine()


@pytest_asyncio.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client
