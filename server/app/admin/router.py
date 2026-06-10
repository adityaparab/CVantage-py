"""Admin API routes (issue #59)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.admin.schemas import AdminStatsResponse
from app.admin.service import get_admin_stats
from app.auth.dependencies import get_current_user, require_role
from app.common.schemas import ErrorEnvelope
from app.database.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    summary="Get platform statistics",
    description="Returns platform-wide statistics. Admin-only endpoint.",
    response_model=AdminStatsResponse,
    responses={
        200: {
            "description": "Platform statistics.",
            "content": {
                "application/json": {
                    "example": {
                        "registeredUsers": 42,
                        "totalResumes": 128,
                        "totalAnalyses": 256,
                    }
                }
            },
        },
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
    },
)
async def stats(
    _current_user: Annotated[User, Depends(get_current_user)],
    _admin_guard: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> AdminStatsResponse:
    stats_data = await get_admin_stats()
    return AdminStatsResponse(
        registeredUsers=stats_data["registered_users"],
        totalResumes=stats_data["total_resumes"],
        totalAnalyses=stats_data["total_analyses"],
    )
