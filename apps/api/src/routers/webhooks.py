"""Razorpay webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import DbSession

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = structlog.get_logger("spectraquant_api.webhooks")


def _posthog_capture_subscription_activated(payload: dict[str, Any]) -> None:
    """Fire subscription_activated event to PostHog via REST API (server-side)."""
    posthog_key = os.getenv("POSTHOG_API_KEY", "")
    if not posthog_key:
        return
    try:
        import httpx  # already in deps

        entity: dict[str, Any] = payload.get("subscription", {}).get("entity", {})
        user_id: str = entity.get("notes", {}).get("user_id", "anonymous")
        httpx.post(
            "https://app.posthog.com/capture/",
            json={
                "api_key": posthog_key,
                "event": "subscription_activated",
                "distinct_id": user_id,
                "properties": {
                    "tier": "pro",
                    "razorpay_subscription_id": entity.get("id", ""),
                },
            },
            timeout=5.0,
        )
    except Exception:  # noqa: BLE001
        pass  # never let analytics block webhook response


def _verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches the request body."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_payment_captured(
    payload: dict[str, Any],
    session: AsyncSession,
) -> None:
    entity: dict[str, Any] = payload.get("payment", {}).get("entity", {})
    razorpay_payment_id: str = entity.get("id", "")
    notes: dict[str, Any] = entity.get("notes", {})
    user_id: str = notes.get("user_id", "")
    amount_paise: int = int(entity.get("amount", 0))
    currency: str = entity.get("currency", "INR")
    captured_at_raw: int | None = entity.get("created_at")

    captured_at: datetime
    if captured_at_raw is not None:
        captured_at = datetime.fromtimestamp(captured_at_raw, tz=UTC)
    else:
        captured_at = datetime.now(tz=UTC)

    await session.execute(
        text(
            """
            INSERT INTO payments (
                razorpay_payment_id,
                user_id,
                amount_paise,
                currency,
                status,
                captured_at
            )
            VALUES (
                :razorpay_payment_id,
                :user_id,
                :amount_paise,
                :currency,
                'captured',
                :captured_at
            )
            ON CONFLICT (razorpay_payment_id) DO NOTHING
            """
        ),
        {
            "razorpay_payment_id": razorpay_payment_id,
            "user_id": user_id,
            "amount_paise": amount_paise,
            "currency": currency,
            "captured_at": captured_at,
        },
    )


async def _handle_subscription_activated(
    payload: dict[str, Any],
    session: AsyncSession,
) -> None:
    entity: dict[str, Any] = payload.get("subscription", {}).get("entity", {})
    razorpay_subscription_id: str = entity.get("id", "")
    notes: dict[str, Any] = entity.get("notes", {})
    user_id: str = notes.get("user_id", "")

    period_start_raw: int | None = entity.get("current_start")
    period_end_raw: int | None = entity.get("current_end")

    period_start: datetime = (
        datetime.fromtimestamp(period_start_raw, tz=UTC)
        if period_start_raw is not None
        else datetime.now(tz=UTC)
    )
    period_end: datetime = (
        datetime.fromtimestamp(period_end_raw, tz=UTC)
        if period_end_raw is not None
        else datetime.now(tz=UTC)
    )

    await session.execute(
        text(
            """
            INSERT INTO subscriptions (
                user_id,
                razorpay_subscription_id,
                status,
                tier,
                period_start,
                period_end
            )
            VALUES (
                :user_id,
                :razorpay_subscription_id,
                'active',
                'pro',
                :period_start,
                :period_end
            )
            ON CONFLICT (razorpay_subscription_id) DO UPDATE
                SET status = 'active'
            """
        ),
        {
            "user_id": user_id,
            "razorpay_subscription_id": razorpay_subscription_id,
            "period_start": period_start,
            "period_end": period_end,
        },
    )


# ---------------------------------------------------------------------------
# POST /webhooks/razorpay
# ---------------------------------------------------------------------------


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    session: AsyncSession = DbSession,
) -> dict[str, str]:
    """Receive and process Razorpay webhook events."""

    settings = get_settings()
    body: bytes = await request.body()

    signature = request.headers.get("X-Razorpay-Signature", "")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Razorpay-Signature header",
        )

    if not settings.razorpay_webhook_secret or not _verify_razorpay_signature(
        body, signature, settings.razorpay_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    try:
        data: dict[str, Any] = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("razorpay_webhook_parse_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc

    event: str = data.get("event", "")
    payload: dict[str, Any] = data.get("payload", {})

    log = logger.bind(event=event)

    if event == "payment.captured":
        log.info("razorpay_payment_captured")
        await _handle_payment_captured(payload, session)
        await session.commit()
        return {"status": "ok"}

    if event == "subscription.activated":
        log.info("razorpay_subscription_activated")
        await _handle_subscription_activated(payload, session)
        await session.commit()
        _posthog_capture_subscription_activated(payload)
        return {"status": "ok"}

    log.info("razorpay_event_ignored")
    return {"status": "ignored"}
