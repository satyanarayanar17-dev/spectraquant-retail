"""Supabase JWT verification helpers."""

from __future__ import annotations

import time
from typing import Annotated, Any, cast

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTClaimsError, JWTError

from src.config import get_settings

_JWKS_CACHE: dict[str, Any] = {
    "jwks": None,
    "expires_at": 0.0,
}
_CACHE_TTL_SECONDS = 300.0
_bearer = HTTPBearer(auto_error=False)
_bearer_dependency = Depends(_bearer)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )


async def _fetch_jwks(force_refresh: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    cached_jwks = _JWKS_CACHE.get("jwks")
    expires_at = float(_JWKS_CACHE.get("expires_at", 0.0))

    if not force_refresh and cached_jwks is not None and now < expires_at:
        return cast(dict[str, Any], cached_jwks)

    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.jwks_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise _unauthorized() from exc

    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise _unauthorized()

    _JWKS_CACHE["jwks"] = payload
    _JWKS_CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return cast(dict[str, Any], payload)


def _select_jwk(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    keys = jwks.get("keys", [])
    if kid is None and len(keys) == 1:
        only_key = keys[0]
        return only_key if isinstance(only_key, dict) else None

    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    return None


async def verify_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase JWT against the cached JWKS endpoint."""

    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _unauthorized() from exc

    jwks = await _fetch_jwks()
    jwk_key = _select_jwk(jwks, header.get("kid"))
    if jwk_key is None:
        jwks = await _fetch_jwks(force_refresh=True)
        jwk_key = _select_jwk(jwks, header.get("kid"))
    if jwk_key is None:
        raise _unauthorized()

    algorithm = header.get("alg", "RS256")

    try:
        claims = jwt.decode(
            token,
            jwk_key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=settings.jwt_issuer,
        )
    except (JWTError, JWTClaimsError) as exc:
        raise _unauthorized() from exc

    aud_claim = claims.get("aud")
    if aud_claim != "authenticated" and (
        not isinstance(aud_claim, list) or "authenticated" not in aud_claim
    ):
        raise _unauthorized()
    if claims.get("iss") != settings.jwt_issuer:
        raise _unauthorized()

    return cast(dict[str, Any], claims)


async def verify_jwt_dependency(
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> dict[str, Any]:
    """FastAPI dependency that extracts and verifies a bearer token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    return await verify_jwt(credentials.credentials)


get_current_user = Depends(verify_jwt_dependency)
CurrentUser = Annotated[dict[str, Any], Depends(verify_jwt_dependency)]


def clear_jwks_cache() -> None:
    """Test helper for cache reset."""

    _JWKS_CACHE["jwks"] = None
    _JWKS_CACHE["expires_at"] = 0.0
