from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.auth.schemas import UserMeResponse
from app.common.schemas import ErrorEnvelope

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    summary="Get current user profile",
    description="Returns the authenticated user's basic profile information.",
    response_model=UserMeResponse,
    responses={
        200: {
            "description": "Authenticated user profile.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "email": "candidate@example.com",
                        "fullName": "Jane Candidate",
                        "role": "candidate",
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
async def me(current_user: CurrentUser) -> UserMeResponse:
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email,
        fullName=current_user.full_name,
        role=current_user.role.value,
    )
