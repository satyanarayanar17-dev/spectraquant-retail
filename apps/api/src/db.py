"""Database engine and session helpers."""

from __future__ import annotations

import base64
import binascii
import sqlite3
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _sqlite_encrypt(plaintext: str, enc_key: str) -> bytes:
    raw = f"{enc_key}:{plaintext}".encode()
    return base64.b64encode(raw)


def _sqlite_decrypt(ciphertext: bytes | str, enc_key: str) -> str:
    payload = ciphertext if isinstance(ciphertext, bytes) else ciphertext.encode("utf-8")
    try:
        decoded = base64.b64decode(payload).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("Invalid encrypted payload") from exc

    prefix = f"{enc_key}:"
    if not decoded.startswith(prefix):
        raise ValueError("Invalid encryption key")
    return decoded.removeprefix(prefix)


def _register_sqlite_functions(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        run_async = getattr(dbapi_connection, "run_async", None)
        if callable(run_async):
            run_async(
                lambda connection: connection.create_function(
                    "pgp_sym_encrypt", 2, _sqlite_encrypt
                )
            )
            run_async(
                lambda connection: connection.create_function(
                    "pgp_sym_decrypt", 2, _sqlite_decrypt
                )
            )
            run_async(lambda connection: connection.execute("PRAGMA foreign_keys = ON"))
            return

        candidate = dbapi_connection
        if not hasattr(candidate, "create_function"):
            driver_connection = getattr(dbapi_connection, "driver_connection", None)
            if driver_connection is not None:
                candidate = driver_connection

        if hasattr(candidate, "create_function"):
            candidate.create_function("pgp_sym_encrypt", 2, _sqlite_encrypt)
            candidate.create_function("pgp_sym_decrypt", 2, _sqlite_decrypt)

        if isinstance(candidate, sqlite3.Connection):
            candidate.execute("PRAGMA foreign_keys = ON")


def get_engine() -> AsyncEngine:
    """Return a cached async engine."""

    global _engine, _session_factory

    if _engine is not None:
        return _engine

    settings = get_settings()
    is_sqlite = settings.supabase_db_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}

    _engine = create_async_engine(
        settings.supabase_db_url,
        pool_pre_ping=not is_sqlite,
        connect_args=connect_args,
    )
    if is_sqlite:
        _register_sqlite_functions(_engine)

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a cached async sessionmaker."""

    global _session_factory

    if _session_factory is None:
        get_engine()

    assert _session_factory is not None
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI database dependency."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


DbSession = Depends(get_db)


async def dispose_engine() -> None:
    """Dispose the cached engine."""

    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
