"""Regression tests: secret fields persist to the DB but stay out of API DTOs.

Previously ``password_hash`` / ``api_key_encrypted`` / ``token_hash`` used
Pydantic ``Field(exclude=True)``, which also drops them from Beanie's stored
document — meaning hashes were never written to Mongo and login/key-resolution
would silently break against a real database. These tests guard the fix:
secrets round-trip through Beanie, and the response DTOs never expose them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from beanie import PydanticObjectId

from app.auth.schemas import UserMeResponse
from app.database.models import AuthToken, TokenKind, User
from app.users.schemas import UserSelfResponse


@pytest.mark.usefixtures("beanie_db")
class TestSecretPersistence:
    @pytest.mark.asyncio
    async def test_user_password_hash_persists(self) -> None:
        user = User(
            email="persist@example.com",
            password_hash="$argon2id$v=19$m=65536$fakehashvalue",
            full_name="Persist Tester",
        )
        await user.insert()

        reloaded = await User.get(user.id)
        assert reloaded is not None
        assert reloaded.password_hash == "$argon2id$v=19$m=65536$fakehashvalue"

    @pytest.mark.asyncio
    async def test_auth_token_hash_persists(self) -> None:
        token = AuthToken(
            user_id=PydanticObjectId(),
            kind=TokenKind.REFRESH,
            token_hash="sha256-of-opaque-token",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        await token.insert()

        reloaded = await AuthToken.find_one({"token_hash": "sha256-of-opaque-token"})
        assert reloaded is not None
        assert reloaded.token_hash == "sha256-of-opaque-token"

    def test_user_response_dtos_have_no_secret_fields(self) -> None:
        # Static guarantee: the API response models cannot carry the hash.
        assert "password_hash" not in UserMeResponse.model_fields
        assert "password_hash" not in UserSelfResponse.model_fields
