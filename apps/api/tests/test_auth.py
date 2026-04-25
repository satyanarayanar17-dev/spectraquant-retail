"""JWT verification tests."""

# ruff: noqa: E402

from __future__ import annotations

import base64
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Request, Response
from jose import jwt

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
CORE_SRC = REPO_ROOT / "packages" / "spectraquant-core" / "src"

for candidate in (str(CORE_SRC), str(API_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_DB_URL", f"sqlite+aiosqlite:///{API_ROOT / 'auth-test.db'}")
os.environ.setdefault("HOLDINGS_ENC_KEY", "test-secret")

from src.auth import CurrentUser, clear_jwks_cache
from src.config import clear_settings_cache


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_key_material() -> tuple[bytes, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_numbers()

    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "alg": "RS256",
        "use": "sig",
        "n": _b64url_uint(public_key.n),
        "e": _b64url_uint(public_key.e),
    }
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem, jwk


class _MockAsyncClient:
    def __init__(self, jwk: dict[str, object], **_: object) -> None:
        self._jwk = jwk

    async def __aenter__(self) -> _MockAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, url: str) -> Response:
        request = Request("GET", url)
        return Response(200, json={"keys": [self._jwk]}, request=request)


async def _make_client(monkeypatch, jwk: dict[str, object]) -> AsyncClient:
    from src import auth

    clear_settings_cache()
    clear_jwks_cache()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **kwargs: _MockAsyncClient(jwk, **kwargs))

    app = FastAPI()

    @app.get("/protected")
    async def protected(_: CurrentUser) -> dict[str, str]:
        return {"status": "ok"}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _token(
    private_key: bytes,
    *,
    aud: str = "authenticated",
    exp_delta: timedelta = timedelta(minutes=15),
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-123",
        "aud": aud,
        "iss": "https://example.supabase.co/auth/v1",
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key"})


async def test_valid_jwt_passes(monkeypatch) -> None:
    private_key, jwk = _build_key_material()
    async with await _make_client(monkeypatch, jwk) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {_token(private_key)}"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_expired_jwt_returns_401(monkeypatch) -> None:
    private_key, jwk = _build_key_material()
    async with await _make_client(monkeypatch, jwk) as client:
        response = await client.get(
            "/protected",
            headers={
                "Authorization": (
                    f"Bearer {_token(private_key, exp_delta=timedelta(minutes=-5))}"
                )
            },
        )

    assert response.status_code == 401


async def test_wrong_audience_returns_401(monkeypatch) -> None:
    private_key, jwk = _build_key_material()
    async with await _make_client(monkeypatch, jwk) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {_token(private_key, aud='public')}"},
        )

    assert response.status_code == 401
