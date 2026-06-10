from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.auth.service import get_user_by_token
from app.config import Settings, get_settings
from app.database.models import User, UserRole, UserStatus

_LAST_ACTIVE_UPDATE_INTERVAL = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _touch_last_active(user: User) -> None:
    now = _utcnow()
    if (
        user.last_active_at is not None
        and (now - user.last_active_at) < _LAST_ACTIVE_UPDATE_INTERVAL
    ):
        return

    user.last_active_at = now
    await user.save()


async def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"message": "Authentication required"})

    token = authorization.split(" ", maxsplit=1)[1]
    user = await get_user_by_token(token, settings)
    if user is None:
        raise HTTPException(status_code=401, detail={"message": "Authentication required"})
    if user.status == UserStatus.DEACTIVATED:
        raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})

    await _touch_last_active(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(required_role: UserRole) -> Callable[[User], Awaitable[User]]:
    async def _role_guard(current_user: CurrentUser) -> User:
        if current_user.role != required_role:
            raise HTTPException(status_code=403, detail={"message": "Forbidden"})
        return current_user

    return _role_guard
