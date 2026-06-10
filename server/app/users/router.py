from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.users.schemas import (
    ChangePasswordRequest,
    DashboardStatsResponse,
    PasswordChangedResponse,
    UserProfileUpdateRequest,
    UserSelfResponse,
)
from app.users.service import (
    change_current_user_password,
    get_dashboard_stats,
    update_current_user_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    summary="Get current user profile",
    description="Returns the authenticated user's sanitized profile and dashboard counters.",
    response_model=UserSelfResponse,
    responses={
        200: {
            "description": "Authenticated user profile.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "email": "candidate@example.com",
                        "fullName": "Jane Candidate",
                        "avatarUrl": "https://cdn.example.com/avatar.png",
                        "role": "candidate",
                        "emailVerified": True,
                        "resumeCount": 3,
                        "analysisCount": 7,
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 401,
                        "error": "Unauthorized",
                        "message": "Authentication required",
                        "path": "/api/v1/users/me",
                    }
                }
            },
        },
        403: {
            "model": ErrorEnvelope,
            "description": "The user account is deactivated.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 403,
                        "error": "Forbidden",
                        "message": "Account is deactivated",
                        "path": "/api/v1/users/me",
                    }
                }
            },
        },
    },
)
async def me(current_user: CurrentUser) -> UserSelfResponse:
    return UserSelfResponse(
        id=str(current_user.id),
        email=current_user.email,
        fullName=current_user.full_name,
        avatarUrl=current_user.avatar_url,
        role=current_user.role.value,
        emailVerified=current_user.email_verified,
        resumeCount=current_user.resume_count,
        analysisCount=current_user.analysis_count,
    )


@router.patch(
    "/me",
    summary="Update current user profile",
    description="Updates the authenticated user's editable profile fields.",
    response_model=UserSelfResponse,
    responses={
        200: {
            "description": "Updated user profile.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "email": "candidate@example.com",
                        "fullName": "Jane Candidate",
                        "avatarUrl": "https://cdn.example.com/new-avatar.png",
                        "role": "candidate",
                        "emailVerified": True,
                        "resumeCount": 3,
                        "analysisCount": 7,
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
        403: {
            "model": ErrorEnvelope,
            "description": "The user account is deactivated.",
        },
    },
)
async def patch_me(
    payload: UserProfileUpdateRequest,
    current_user: CurrentUser,
) -> UserSelfResponse:
    updated = await update_current_user_profile(current_user, payload)
    return UserSelfResponse(
        id=str(updated.id),
        email=updated.email,
        fullName=updated.full_name,
        avatarUrl=updated.avatar_url,
        role=updated.role.value,
        emailVerified=updated.email_verified,
        resumeCount=updated.resume_count,
        analysisCount=updated.analysis_count,
    )


@router.post(
    "/me/password",
    summary="Change current user password",
    description=(
        "Changes the authenticated user's password after verifying the current password. "
        "All refresh sessions are revoked."
    ),
    response_model=PasswordChangedResponse,
    responses={
        200: {
            "description": "Password updated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                    }
                }
            },
        },
        403: {
            "model": ErrorEnvelope,
            "description": "Current password is incorrect or account is not eligible.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 403,
                        "error": "Forbidden",
                        "message": "Current password is incorrect",
                        "path": "/api/v1/users/me/password",
                    }
                }
            },
        },
    },
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
) -> PasswordChangedResponse:
    await change_current_user_password(current_user, payload)
    return PasswordChangedResponse(status="ok")


@router.get(
    "/me/stats",
    summary="Get dashboard statistics",
    description=(
        "Returns the authenticated user's dashboard counters: "
        "resume count and analysis count. Counters are maintained "
        "atomically via $inc on create/delete operations."
    ),
    response_model=DashboardStatsResponse,
    responses={
        200: {
            "description": "Dashboard statistics.",
            "content": {
                "application/json": {
                    "example": {"resumeCount": 3, "analysisCount": 7},
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
    },
)
async def me_stats(current_user: CurrentUser) -> DashboardStatsResponse:
    stats = await get_dashboard_stats(current_user)
    return DashboardStatsResponse(
        resumeCount=stats.resume_count,
        analysisCount=stats.analysis_count,
    )
