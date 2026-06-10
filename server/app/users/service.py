from __future__ import annotations

from fastapi import HTTPException

from app.auth.passwords import hash_password, verify_password
from app.auth.service import _revoke_user_refresh_family, _validate_password_strength
from app.database.models import User
from app.users.schemas import ChangePasswordRequest, UserProfileUpdateRequest


async def update_current_user_profile(
    current_user: User,
    payload: UserProfileUpdateRequest,
) -> User:
    if payload.full_name is None and payload.avatar_url is None:
        return current_user

    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    current_user.avatar_url = payload.avatar_url
    await current_user.save()
    return current_user


async def change_current_user_password(
    current_user: User,
    payload: ChangePasswordRequest,
) -> None:
    if current_user.password_hash is None or not verify_password(
        payload.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(status_code=403, detail={"message": "Current password is incorrect"})

    _validate_password_strength(payload.new_password)
    current_user.password_hash = hash_password(payload.new_password)
    await current_user.save()
    await _revoke_user_refresh_family(current_user.id)
