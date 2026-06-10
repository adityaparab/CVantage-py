import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.auth.schemas import (
    AcceptedResponse,
    AuthTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutResponse,
    OAuthAuthorizationResponse,
    OAuthProvidersResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SuccessResponse,
    UserMeResponse,
    VerifyEmailRequest,
)
from app.auth.service import (
    build_oauth_authorization_url,
    login_user,
    logout_user_session,
    oauth_callback_login,
    oauth_provider_flags,
    refresh_user_session,
    register_user,
    request_password_reset,
    reset_password_with_token,
    verify_email_with_token,
)
from app.common.schemas import ErrorEnvelope
from app.config import Settings, get_settings
from app.database.models import OAuthProvider
from app.security.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _parse_provider_or_404(provider: str) -> OAuthProvider:
    try:
        parsed = OAuthProvider(provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"message": "OAuth provider is disabled"},
        ) from exc
    return parsed


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


@router.get(
    "/providers",
    summary="Get OAuth provider availability",
    description="Returns whether Google and LinkedIn OAuth logins are currently enabled.",
    response_model=OAuthProvidersResponse,
    responses={
        200: {
            "description": "OAuth provider availability flags.",
            "content": {
                "application/json": {
                    "example": {
                        "google": True,
                        "linkedin": False,
                    }
                }
            },
        }
    },
)
async def providers(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthProvidersResponse:
    flags = oauth_provider_flags(settings)
    return OAuthProvidersResponse(google=flags["google"], linkedin=flags["linkedin"])


@router.get(
    "/oauth/{provider}/login",
    summary="Start OAuth login",
    description="Initiates OAuth/OIDC login by redirecting to the configured provider.",
    response_model=OAuthAuthorizationResponse,
    responses={
        200: {
            "description": "Provider authorization URL and CSRF cookies are issued.",
            "content": {
                "application/json": {
                    "example": {
                        "authorizationUrl": "https://accounts.google.com/o/oauth2/v2/auth?...",
                    }
                }
            },
        },
        404: {
            "model": ErrorEnvelope,
            "description": "OAuth provider is disabled.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 404,
                        "error": "Not Found",
                        "message": "OAuth provider is disabled",
                        "path": "/api/v1/auth/oauth/google/login",
                    }
                }
            },
        },
    },
)
async def oauth_login(
    provider: str,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OAuthAuthorizationResponse:
    parsed_provider = _parse_provider_or_404(provider)
    flags = oauth_provider_flags(settings)
    if not flags[parsed_provider.value]:
        raise HTTPException(status_code=404, detail={"message": "OAuth provider is disabled"})

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    authorization_url = await build_oauth_authorization_url(parsed_provider, settings, state, nonce)
    cookie_path = f"/api/v1/auth/oauth/{parsed_provider.value}"
    response.set_cookie(
        key=f"cv_oauth_{parsed_provider.value}_state",
        value=state,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=600,
        path=cookie_path,
    )
    response.set_cookie(
        key=f"cv_oauth_{parsed_provider.value}_nonce",
        value=nonce,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=600,
        path=cookie_path,
    )
    return OAuthAuthorizationResponse(authorizationUrl=authorization_url)


@router.get(
    "/oauth/{provider}/callback",
    summary="Handle OAuth callback",
    description=(
        "Validates OAuth state/nonce and completes login by linking or creating the user account."
    ),
    response_model=AuthTokenResponse,
    responses={
        200: {
            "description": "OAuth callback succeeded and access token issued.",
            "content": {
                "application/json": {
                    "example": {
                        "accessToken": "signed-token",
                        "tokenType": "bearer",
                    }
                }
            },
        },
        400: {
            "model": ErrorEnvelope,
            "description": "Invalid callback state or profile payload.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": "Invalid oauth state",
                        "path": "/api/v1/auth/oauth/google/callback",
                    }
                }
            },
        },
        404: {
            "model": ErrorEnvelope,
            "description": "OAuth provider is disabled.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 404,
                        "error": "Not Found",
                        "message": "OAuth provider is disabled",
                        "path": "/api/v1/auth/oauth/google/callback",
                    }
                }
            },
        },
        409: {
            "model": ErrorEnvelope,
            "description": "OAuth identity conflicts with another account.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 409,
                        "error": "Conflict",
                        "message": "OAuth identity already linked",
                        "path": "/api/v1/auth/oauth/google/callback",
                    }
                }
            },
        },
    },
)
async def oauth_callback(
    provider: str,
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokenResponse:
    parsed_provider = _parse_provider_or_404(provider)
    flags = oauth_provider_flags(settings)
    if not flags[parsed_provider.value]:
        raise HTTPException(status_code=404, detail={"message": "OAuth provider is disabled"})

    expected_state = request.cookies.get(f"cv_oauth_{parsed_provider.value}_state")
    nonce = request.cookies.get(f"cv_oauth_{parsed_provider.value}_nonce")
    if not expected_state or expected_state != state or not nonce:
        raise HTTPException(status_code=400, detail={"message": "Invalid oauth state"})

    access_token, refresh_token = await oauth_callback_login(
        parsed_provider,
        code,
        nonce,
        settings,
        request,
    )
    cookie_path = f"/api/v1/auth/oauth/{parsed_provider.value}"
    response.delete_cookie(key=f"cv_oauth_{parsed_provider.value}_state", path=cookie_path)
    response.delete_cookie(key=f"cv_oauth_{parsed_provider.value}_nonce", path=cookie_path)
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
    "/forgot-password",
    summary="Request password reset",
    description=(
        "Queues a password reset email when the account exists. Always returns 202 to "
        "avoid user enumeration."
    ),
    response_model=AcceptedResponse,
    responses={
        202: {
            "description": "Password reset request accepted.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "accepted",
                    }
                }
            },
        }
    },
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    response: Response,
) -> AcceptedResponse:
    response.status_code = 202
    await request_password_reset(payload.email, settings)
    return AcceptedResponse(status="accepted")


@router.post(
    "/reset-password",
    summary="Reset password with token",
    description="Consumes a single-use password reset token and updates user password.",
    response_model=SuccessResponse,
    responses={
        200: {
            "description": "Password reset completed.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                    }
                }
            },
        },
        400: {
            "model": ErrorEnvelope,
            "description": "Reset token is invalid, reused, or expired.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": "Invalid or expired token",
                        "path": "/api/v1/auth/reset-password",
                    }
                }
            },
        },
    },
)
async def reset_password(
    payload: ResetPasswordRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SuccessResponse:
    await reset_password_with_token(payload.token, payload.new_password, settings)
    return SuccessResponse(status="ok")


@router.post(
    "/verify-email",
    summary="Verify email with token",
    description="Consumes a single-use email verification token and marks account as verified.",
    response_model=SuccessResponse,
    responses={
        200: {
            "description": "Email verification succeeded.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                    }
                }
            },
        },
        400: {
            "model": ErrorEnvelope,
            "description": "Verification token is invalid, reused, or expired.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": "Invalid or expired token",
                        "path": "/api/v1/auth/verify-email",
                    }
                }
            },
        },
    },
)
async def verify_email(payload: VerifyEmailRequest) -> SuccessResponse:
    await verify_email_with_token(payload.token)
    return SuccessResponse(status="ok")
