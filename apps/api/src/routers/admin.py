"""Admin-only routes (founder-gated)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUser
from src.config import get_settings
from src.db import DbSession

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# GET /admin/jobs
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_job_runs(
    current_user: CurrentUser,
    session: AsyncSession = DbSession,
) -> dict[str, object]:
    """Return recent job run history. Restricted to the founder email."""

    settings = get_settings()
    caller_email: str = current_user.get("email", "")

    if not settings.founder_email or caller_email != settings.founder_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )

    result = await session.execute(
        text(
            """
            SELECT job_name, status, rows_written, started_at, finished_at
            FROM job_runs
            ORDER BY started_at DESC
            LIMIT 100
            """
        )
    )
    jobs = [dict(row) for row in result.mappings().all()]

    return {"jobs": jobs}
