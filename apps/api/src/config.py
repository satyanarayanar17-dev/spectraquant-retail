"""Runtime configuration helpers for the API app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Resolved environment settings."""

    supabase_url: str
    supabase_db_url: str
    holdings_enc_key: str
    allowed_origins: tuple[str, ...]
    log_level: str
    founder_email: str = ""
    razorpay_webhook_secret: str = ""
    version: str = "0.1.0"

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


_DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "https://spectraquant.in",
    "https://www.spectraquant.in",
)


def _parse_allowed_origins(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None or not raw_value.strip():
        return _DEFAULT_ALLOWED_ORIGINS
    return tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings(
        supabase_url=_require_env("SUPABASE_URL"),
        supabase_db_url=_require_env("SUPABASE_DB_URL"),
        holdings_enc_key=_require_env("HOLDINGS_ENC_KEY"),
        allowed_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        founder_email=os.getenv("FOUNDER_EMAIL", ""),
        razorpay_webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
    )


def clear_settings_cache() -> None:
    """Test helper to force settings re-resolution."""

    get_settings.cache_clear()

