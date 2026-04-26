"""User account management routes (DPDP-compliant deletion, data export, billing cancel)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.db import DbSession

router = APIRouter(prefix="/api/v1/user", tags=["user"])
billing_router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# DELETE /api/v1/user/me
# ---------------------------------------------------------------------------


@router.delete("/me")
async def delete_me(
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> dict[str, str]:
    """Soft-delete the authenticated user and schedule hard deletion after 30 days."""

    user_id: str = current_user["sub"]

    await session.execute(
        text(
            "UPDATE profiles SET deleted_at = NOW() WHERE id = :user_id AND deleted_at IS NULL"
        ),
        {"user_id": user_id},
    )

    await session.execute(
        text(
            "UPDATE portfolios SET deleted_at = NOW()"
            " WHERE user_id = :user_id AND deleted_at IS NULL"
        ),
        {"user_id": user_id},
    )

    result = await session.execute(
        text(
            """
            INSERT INTO scheduled_deletions (user_id, delete_after)
            VALUES (:user_id, NOW() + INTERVAL '30 days')
            RETURNING delete_after
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    await session.commit()

    delete_after: datetime = row["delete_after"]  # type: ignore[index]
    if delete_after.tzinfo is None:
        delete_after = delete_after.replace(tzinfo=UTC)

    return {
        "status": "deletion_scheduled",
        "delete_after": delete_after.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/user/me/export
# ---------------------------------------------------------------------------


@router.get("/me/export")
async def export_me(
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> dict[str, object]:
    """Return all personal data for the authenticated user (DPDP data portability)."""

    user_id: str = current_user["sub"]

    profile_result = await session.execute(
        text(
            "SELECT id, created_at FROM profiles WHERE id = :user_id"
        ),
        {"user_id": user_id},
    )
    profile_row = profile_result.mappings().first()

    profile: dict[str, object]
    if profile_row is not None:
        created_at: datetime = profile_row["created_at"]
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        profile = {
            "id": str(profile_row["id"]),
            "email": current_user.get("email", ""),
            "created_at": (
                created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
            ),
        }
    else:
        profile = {
            "id": user_id,
            "email": current_user.get("email", ""),
            "created_at": None,
        }

    portfolios_result = await session.execute(
        text(
            """
            SELECT name, num_holdings
            FROM portfolios
            WHERE user_id = :user_id AND deleted_at IS NULL
            ORDER BY created_at ASC
            """
        ),
        {"user_id": user_id},
    )
    portfolios = [
        {"name": r["name"], "num_holdings": r["num_holdings"]}
        for r in portfolios_result.mappings().all()
    ]

    analyses_count = 0
    try:
        analyses_result = await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM analyses WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        )
        count_row = analyses_result.mappings().first()
        if count_row is not None:
            analyses_count = int(count_row["cnt"])
    except Exception:  # noqa: BLE001
        analyses_count = 0

    return {
        "user_id": user_id,
        "exported_at": datetime.now(tz=UTC).isoformat(),
        "profile": profile,
        "portfolios": portfolios,
        "analyses_count": analyses_count,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/billing/cancel
# ---------------------------------------------------------------------------


@billing_router.post("/cancel")
async def cancel_subscription(
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> dict[str, str]:
    """Cancel the user's active subscription; access continues until period_end."""

    user_id: str = current_user["sub"]

    result = await session.execute(
        text(
            """
            UPDATE subscriptions
            SET
                cancelled_at = NOW(),
                tier_downgrade_at = period_end
            WHERE user_id = :user_id
              AND cancelled_at IS NULL
              AND status = 'active'
            RETURNING period_end
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    await session.commit()

    period_end: datetime = row["period_end"]
    if isinstance(period_end, datetime) and period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=UTC)

    return {
        "status": "cancelled",
        "access_until": (
            period_end.isoformat() if isinstance(period_end, datetime) else str(period_end)
        ),
    }
