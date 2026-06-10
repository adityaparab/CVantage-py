from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings


def create_access_token(user_id: str, settings: Settings) -> str:
    serializer = URLSafeTimedSerializer(settings.auth_access_token_secret)
    return serializer.dumps({"sub": user_id})


def decode_access_token(token: str, settings: Settings) -> str | None:
    serializer = URLSafeTimedSerializer(settings.auth_access_token_secret)
    try:
        payload = serializer.loads(token, max_age=settings.auth_access_token_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    return subject
