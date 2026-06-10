from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request

from app.auth.passwords import hash_password, verify_password
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.tokens import create_access_token, decode_access_token
from app.config import Settings
from app.database.models import (
    AuditAction,
    AuditLog,
    AuthToken,
    TokenKind,
    User,
    UserRole,
    UserStatus,
)

_PASSWORD_POLICY_DETAILS = {
    "min_length": 12,
    "requires_uppercase": True,
    "requires_lowercase": True,
    "requires_digit": True,
    "requires_special": True,
}
_SPECIAL_CHAR_RE = re.compile(r"[^A-Za-z0-9]")
_DUMMY_PASSWORD_HASH = hash_password("cvantage-dummy-password")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _revoke_user_refresh_family(user_id: object) -> None:
    active_tokens = await AuthToken.find(
        {
            "user_id": user_id,
            "kind": TokenKind.REFRESH,
            "consumed_at": None,
        }
    ).to_list()
    revoked_at = _utcnow()
    for token in active_tokens:
        token.consumed_at = revoked_at
        await token.save()


async def _issue_refresh_token(user: User, settings: Settings, request: Request) -> str:
    refresh_token = _new_refresh_token()
    expires_at = _utcnow() + timedelta(days=settings.auth_refresh_token_ttl_days)
    await AuthToken(
        user_id=user.id,
        kind=TokenKind.REFRESH,
        token_hash=_hash_refresh_token(refresh_token),
        expires_at=expires_at,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
    ).insert()
    return refresh_token


def _invalid_refresh_token_error() -> HTTPException:
    return HTTPException(status_code=401, detail={"message": "Invalid refresh token"})


def _validate_password_strength(password: str) -> None:
    strong = (
        len(password) >= _PASSWORD_POLICY_DETAILS["min_length"]
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
        and any(c.isdigit() for c in password)
        and _SPECIAL_CHAR_RE.search(password) is not None
    )

    if strong:
        return

    raise HTTPException(
        status_code=422,
        detail={
            "message": "Password policy requirements not met",
            "policy": _PASSWORD_POLICY_DETAILS,
        },
    )


async def register_user(payload: RegisterRequest, settings: Settings) -> User:
    _validate_password_strength(payload.password)

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.CANDIDATE,
        status=UserStatus.ACTIVE,
    )

    try:
        await user.insert()
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "Email already registered"},
        ) from exc

    await AuditLog(
        actor_id=user.id,
        action=AuditAction.USER_REGISTER,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
    ).insert()

    _ = settings
    return user


async def login_user(
    payload: LoginRequest,
    settings: Settings,
    request: Request,
) -> tuple[str, str]:
    user = await User.find_one(User.email == payload.email.lower().strip())
    if user is None:
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})

    if user.password_hash is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})

    if user.status == UserStatus.DEACTIVATED:
        raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})

    await AuditLog(
        actor_id=user.id,
        action=AuditAction.USER_LOGIN,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
        ip=_client_ip(request),
    ).insert()

    access_token = create_access_token(str(user.id), settings)
    refresh_token = await _issue_refresh_token(user, settings, request)
    return access_token, refresh_token


async def refresh_user_session(
    refresh_token: str,
    settings: Settings,
    request: Request,
) -> tuple[str, str]:
    token_hash = _hash_refresh_token(refresh_token)
    stored_token = await AuthToken.find_one(
        {
            "kind": TokenKind.REFRESH,
            "token_hash": token_hash,
        }
    )
    if stored_token is None:
        raise _invalid_refresh_token_error()

    if stored_token.consumed_at is not None:
        await _revoke_user_refresh_family(stored_token.user_id)
        await AuditLog(
            actor_id=stored_token.user_id,
            action=AuditAction.USER_LOGIN,
            target_type="user",
            target_id=stored_token.user_id,
            meta={"event": "refresh_reuse_detected"},
            ip=_client_ip(request),
        ).insert()
        raise _invalid_refresh_token_error()

    now = _utcnow()
    if stored_token.expires_at <= now:
        stored_token.consumed_at = now
        await stored_token.save()
        raise _invalid_refresh_token_error()

    user = await User.get(stored_token.user_id)
    if user is None:
        raise _invalid_refresh_token_error()
    if user.status == UserStatus.DEACTIVATED:
        raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})

    stored_token.consumed_at = now
    await stored_token.save()

    new_access = create_access_token(str(user.id), settings)
    new_refresh = await _issue_refresh_token(user, settings, request)
    return new_access, new_refresh


async def logout_user_session(refresh_token: str | None, request: Request) -> None:
    if not refresh_token:
        return

    token_hash = _hash_refresh_token(refresh_token)
    stored_token = await AuthToken.find_one(
        {
            "kind": TokenKind.REFRESH,
            "token_hash": token_hash,
        }
    )
    if stored_token is None:
        return

    await _revoke_user_refresh_family(stored_token.user_id)
    await AuditLog(
        actor_id=stored_token.user_id,
        action=AuditAction.USER_LOGIN,
        target_type="user",
        target_id=stored_token.user_id,
        meta={"event": "logout"},
        ip=_client_ip(request),
    ).insert()


async def get_user_by_token(token: str, settings: Settings) -> User | None:
    user_id = decode_access_token(token, settings)
    if user_id is None:
        return None
    return await User.get(user_id)
