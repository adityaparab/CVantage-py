"""Admin API routes (issues #59, #60)."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Path, Query

from app.admin.schemas import (
    AdminActionResponse,
    AdminPasswordResetRequest,
    AdminPasswordResetResponse,
    AdminResumeListItem,
    AdminResumeListResponse,
    AdminStatsResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from app.admin.service import (
    _user_to_item,
    admin_delete_resume,
    deactivate_user,
    get_admin_stats,
    get_user_or_404,
    list_user_resumes,
    list_users,
    reactivate_user,
    reset_user_password,
    update_user,
)
from app.auth.dependencies import require_role
from app.common.schemas import ErrorEnvelope
from app.config import Settings, get_settings
from app.database.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])

# The role guard returns the authenticated admin, so handlers get the actor.
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def _to_list_item(row: dict[str, object]) -> AdminUserListItem:
    return AdminUserListItem.model_validate(row)


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
async def stats(_admin: AdminUser) -> AdminStatsResponse:
    stats_data = await get_admin_stats()
    return AdminStatsResponse(
        registeredUsers=stats_data["registered_users"],
        totalResumes=stats_data["total_resumes"],
        totalAnalyses=stats_data["total_analyses"],
    )


@router.get(
    "/users",
    summary="List users",
    description=(
        "Paginated, sortable list of users with search by id, email, or name. "
        "Returns metadata only (no resume or analysis content)."
    ),
    response_model=AdminUserListResponse,
    responses={
        200: {"description": "Paginated user list."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
    },
)
async def get_users(
    _admin: AdminUser,
    search: Annotated[str | None, Query(description="Match id, email, or full name")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: Annotated[str, Query(description="created_at|last_active_at|full_name|email")] = (
        "created_at"
    ),
    descending: Annotated[bool, Query()] = True,
) -> AdminUserListResponse:
    data = await list_users(search, skip, limit, sort_by, descending)
    return AdminUserListResponse(
        items=[_to_list_item(r) for r in data["items"]],
        total=data["total"],
        skip=data["skip"],
        limit=data["limit"],
    )


@router.get(
    "/users/{user_id}",
    summary="Get a single user",
    description="Returns one user's metadata. Admin-only.",
    response_model=AdminUserListItem,
    responses={
        200: {"description": "User metadata."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
    },
)
async def get_user_detail(
    _admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
) -> AdminUserListItem:
    user = await get_user_or_404(user_id)
    return _to_list_item(_user_to_item(user))


@router.patch(
    "/users/{user_id}",
    summary="Update a user",
    description="Update a user's full name and/or email (email uniqueness enforced). Audited.",
    response_model=AdminUserListItem,
    responses={
        200: {"description": "Updated user metadata."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
        409: {"model": ErrorEnvelope, "description": "Email already in use."},
    },
)
async def patch_user(
    admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
    payload: AdminUserUpdateRequest,
) -> AdminUserListItem:
    user = await update_user(user_id, admin.id, payload.full_name, payload.email)
    return _to_list_item(_user_to_item(user))


@router.post(
    "/users/{user_id}/reset-password",
    summary="Reset a user's password",
    description=(
        "Either set a temporary password (when `newPassword` is provided) or trigger a "
        "password-reset email. Both revoke active sessions and are audited."
    ),
    response_model=AdminPasswordResetResponse,
    responses={
        200: {"description": "Password reset initiated."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
    },
)
async def post_reset_password(
    admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
    payload: AdminPasswordResetRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminPasswordResetResponse:
    method = await reset_user_password(user_id, admin.id, payload.new_password, settings)
    return AdminPasswordResetResponse(status="ok", method=method)


@router.post(
    "/users/{user_id}/deactivate",
    summary="Deactivate a user",
    description="Deactivates a user and revokes all refresh tokens. Admins cannot self-deactivate.",
    response_model=AdminActionResponse,
    responses={
        200: {"description": "User deactivated."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
        422: {"model": ErrorEnvelope, "description": "Cannot deactivate your own account."},
    },
)
async def post_deactivate_user(
    admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
) -> AdminActionResponse:
    assert admin.id is not None
    await deactivate_user(user_id, admin.id)
    return AdminActionResponse(status="ok")


@router.post(
    "/users/{user_id}/reactivate",
    summary="Reactivate a user",
    description="Re-enables a previously deactivated user. Audited.",
    response_model=AdminActionResponse,
    responses={
        200: {"description": "User reactivated."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
    },
)
async def post_reactivate_user(
    admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
) -> AdminActionResponse:
    assert admin.id is not None
    await reactivate_user(user_id, admin.id)
    return AdminActionResponse(status="ok")


@router.get(
    "/users/{user_id}/resumes",
    summary="List a user's resumes (metadata only)",
    description=(
        "Returns metadata for a user's resumes — name, source, status, counts, dates. "
        "Never returns resume or analysis content (PROMPT.md privacy requirement)."
    ),
    response_model=AdminResumeListResponse,
    responses={
        200: {"description": "Resume metadata list."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "User not found."},
    },
)
async def get_user_resumes(
    _admin: AdminUser,
    user_id: Annotated[PydanticObjectId, Path(description="The user's ObjectId")],
) -> AdminResumeListResponse:
    data = await list_user_resumes(user_id)
    return AdminResumeListResponse(
        items=[AdminResumeListItem.model_validate(r) for r in data["items"]],
        total=data["total"],
    )


@router.delete(
    "/resumes/{resume_id}",
    summary="Delete a resume (cascade)",
    description=(
        "Soft-deletes a resume and cascades the soft-delete to its analyses, clearing "
        "their notifications. Ordered idempotent operations; re-running is a no-op. Audited."
    ),
    response_model=AdminActionResponse,
    responses={
        200: {"description": "Resume deleted (cascade complete)."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        403: {"model": ErrorEnvelope, "description": "User is not an admin."},
        404: {"model": ErrorEnvelope, "description": "Resume not found."},
    },
)
async def delete_resume(
    admin: AdminUser,
    resume_id: Annotated[PydanticObjectId, Path(description="The resume's ObjectId")],
) -> AdminActionResponse:
    await admin_delete_resume(resume_id, admin.id)
    return AdminActionResponse(status="ok")
