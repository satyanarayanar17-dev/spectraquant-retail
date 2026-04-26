"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.config import get_settings
from src.db import dispose_engine
from src.logging import configure_logging
from src.routers import admin, analysis, factors, portfolio, user, webhooks


def create_app() -> FastAPI:
    """Create the configured FastAPI application."""

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        logger = structlog.get_logger("spectraquant_api")
        logger.info(
            "api_startup",
            version=__version__,
            allowed_origins=list(settings.allowed_origins),
        )
        yield
        await dispose_engine()
        logger.info("api_shutdown", version=__version__)

    app = FastAPI(
        title="SpectraQuant Retail API",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(portfolio.router)
    app.include_router(analysis.router)
    app.include_router(factors.router)
    app.include_router(user.router)
    app.include_router(user.billing_router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
