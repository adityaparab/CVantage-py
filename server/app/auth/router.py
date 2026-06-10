from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserMeResponse
from app.auth.service import login_user, register_user
from app.common.schemas import ErrorEnvelope
from app.config import Settings, get_settings
from app.security.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    summary="Register local account",
    description=(
        "Creates a local candidate account using email, full name and password. "
        "Passwords must satisfy the configured strength policy."
    ),
    response_model=UserMeResponse,
    responses={
        200: {
            "description": "Account created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "email": "candidate@example.com",
                        "fullName": "Jane Candidate",
                        "role": "candidate",
                    },
                }
            },
        },
        409: {
            "model": ErrorEnvelope,
            "description": "An account with this email already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 409,
                        "error": "Conflict",
                        "message": "Email already registered",
                        "path": "/api/v1/auth/register",
                    }
                }
            },
        },
        422: {
            "model": ErrorEnvelope,
            "description": "Password does not satisfy policy requirements.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 422,
                        "error": "Unprocessable Entity",
                        "message": "Password policy requirements not met",
                        "path": "/api/v1/auth/register",
                        "details": {
                            "policy": {
                                "min_length": 12,
                                "requires_uppercase": True,
                                "requires_lowercase": True,
                                "requires_digit": True,
                                "requires_special": True,
                            }
                        },
                    }
                }
            },
        },
    },
)
async def register(
    payload: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserMeResponse:
    user = await register_user(payload, settings)
    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        fullName=user.full_name,
        role=user.role.value,
    )


@router.post(
    "/login",
    summary="Authenticate local account",
    description="Authenticates a local account and returns a bearer access token.",
    response_model=AuthTokenResponse,
    responses={
        200: {
            "description": "Authentication succeeded.",
            "content": {
                "application/json": {
                    "example": {
                        "accessToken": "signed-token",
                        "tokenType": "bearer",
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Unknown email or invalid password.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 401,
                        "error": "Unauthorized",
                        "message": "Invalid email or password",
                        "path": "/api/v1/auth/login",
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
                        "path": "/api/v1/auth/login",
                    }
                }
            },
        },
        429: {
            "model": ErrorEnvelope,
            "description": "Too many auth attempts in the configured time window.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 429,
                        "error": "Too Many Requests",
                        "message": "Rate limit exceeded",
                        "path": "/api/v1/auth/login",
                    }
                }
            },
        },
    },
)
@limiter.limit("60/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokenResponse:
    _ = request
    token = await login_user(payload, settings)
    return AuthTokenResponse(accessToken=token, tokenType="bearer")
