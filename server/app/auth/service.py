from __future__ import annotations

import re

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.auth.passwords import hash_password, verify_password
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.tokens import create_access_token, decode_access_token
from app.config import Settings
from app.database.models import AuditAction, AuditLog, User, UserRole, UserStatus

_PASSWORD_POLICY_DETAILS = {
    "min_length": 12,
    "requires_uppercase": True,
    "requires_lowercase": True,
    "requires_digit": True,
    "requires_special": True,
}
_SPECIAL_CHAR_RE = re.compile(r"[^A-Za-z0-9]")
_DUMMY_PASSWORD_HASH = hash_password("cvantage-dummy-password")


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


async def login_user(payload: LoginRequest, settings: Settings) -> str:
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
    ).insert()

    return create_access_token(str(user.id), settings)


async def get_user_by_token(token: str, settings: Settings) -> User | None:
    user_id = decode_access_token(token, settings)
    if user_id is None:
        return None
    return await User.get(user_id)
