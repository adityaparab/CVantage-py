from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.auth.service import get_user_by_token
from app.config import Settings, get_settings
from app.database.models import User, UserStatus


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
    return user
