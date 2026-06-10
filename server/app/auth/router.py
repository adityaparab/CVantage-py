from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    UserMeResponse,
)
from app.auth.service import login_user, logout_user_session, refresh_user_session, register_user
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
    response: Response,
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokenResponse:
    access_token, refresh_token = await login_user(payload, settings, request)
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_refresh_token_ttl_days * 24 * 3600,
        path="/api/v1/auth",
    )
    return AuthTokenResponse(accessToken=access_token, tokenType="bearer")


@router.post(
    "/refresh",
    summary="Rotate refresh token",
    description=(
        "Consumes the current refresh token cookie, rotates it, and returns "
        "a new access token plus a new refresh cookie."
    ),
    response_model=AuthTokenResponse,
    responses={
        200: {
            "description": "Refresh token accepted and rotated.",
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
            "description": "Refresh token is missing, invalid, expired, or reused.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 401,
                        "error": "Unauthorized",
                        "message": "Invalid refresh token",
                        "path": "/api/v1/auth/refresh",
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
                        "path": "/api/v1/auth/refresh",
                    }
                }
            },
        },
    },
)
async def refresh(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokenResponse:
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=401, detail={"message": "Invalid refresh token"})

    access_token, rotated_refresh_token = await refresh_user_session(
        refresh_token,
        settings,
        request,
    )
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=rotated_refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_refresh_token_ttl_days * 24 * 3600,
        path="/api/v1/auth",
    )
    return AuthTokenResponse(accessToken=access_token, tokenType="bearer")


@router.post(
    "/logout",
    summary="Logout current session",
    description="Revokes refresh tokens for the current session family and clears auth cookies.",
    response_model=LogoutResponse,
    responses={
        200: {
            "description": "Session revoked and cookie cleared.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                    }
                }
            },
        }
    },
)
async def logout(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogoutResponse:
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    await logout_user_session(refresh_token, request)
    response.delete_cookie(key=settings.auth_refresh_cookie_name, path="/api/v1/auth")
    return LogoutResponse(status="ok")
