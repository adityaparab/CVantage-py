from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from app.config import Settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: str, settings: Settings) -> str:
    now = _utcnow()
    expires_at = now + timedelta(seconds=settings.auth_access_token_ttl_seconds)
    payload = {
        "sub": user_id,
        "iss": settings.auth_jwt_issuer,
        "aud": settings.auth_jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.auth_access_token_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.auth_access_token_secret,
            algorithms=["HS256"],
            issuer=settings.auth_jwt_issuer,
            audience=settings.auth_jwt_audience,
            options={"require": ["sub", "iss", "aud", "exp", "iat", "nbf"]},
        )
    except InvalidTokenError:
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    return subject
