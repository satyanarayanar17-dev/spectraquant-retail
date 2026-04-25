"""Structlog configuration helpers."""

from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str) -> None:
    """Configure stdlib logging and structlog JSON rendering."""

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

