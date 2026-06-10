"""Tests for the AI model registry service (issue #47, consolidated in #55).

Exercises the real ``AiModelService`` against an in-memory Beanie client:
encrypted-key storage, masked listing, status/rotate/delete, and the
DB-model -> env-fallback resolution order.
"""

from __future__ import annotations

from typing import Any

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.ai.crypto import CryptoService
from app.ai.models import AiModelService, _mask_key
from app.config import Settings
from app.database.models import AiModelStatus, AiModelUsage

# A deterministic 32-byte base64 key for AES-256-GCM.
_TEST_MASTER_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


def _service(*, openai_api_key: str | None = None) -> AiModelService:
    settings = Settings(
        environment="test",
        master_encryption_key=_TEST_MASTER_KEY,
        openai_api_key=openai_api_key,
    )
    crypto = CryptoService(settings.master_encryption_key)
    return AiModelService(crypto, settings)


def _actor() -> PydanticObjectId:
    return PydanticObjectId()


class TestMaskKey:
    def test_long_key_returns_last4(self) -> None:
        assert _mask_key("sk-abcdef1234") == "1234"

    def test_short_key_padded(self) -> None:
        assert _mask_key("ab") == "****ab"

    def test_empty_key(self) -> None:
        assert _mask_key("") == "****"


@pytest.mark.usefixtures("beanie_db")
class TestAiModelService:
    @pytest.mark.asyncio
    async def test_create_encrypts_key_and_stores_last4(self) -> None:
        svc = _service()
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-secret-value-9999",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        assert model.api_key_last4 == "9999"
        # Ciphertext must never equal the raw key.
        assert model.api_key_encrypted != "sk-secret-value-9999"
        # And must round-trip back to the original via the same crypto service.
        decrypted = svc._crypto.decrypt(model.api_key_encrypted)
        assert decrypted == "sk-secret-value-9999"

    @pytest.mark.asyncio
    async def test_create_duplicate_provider_model_conflicts(self) -> None:
        svc = _service()
        await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-aaaa1111",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        with pytest.raises(HTTPException) as exc:
            await svc.create(
                model_name="gpt-4o",
                provider="openai",
                api_key="sk-bbbb2222",
                usages=[AiModelUsage.ANALYSIS],
                added_by=_actor(),
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_list_all_masks_keys(self) -> None:
        svc = _service()
        await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-secret-token-4242",
            usages=[AiModelUsage.ANALYSIS, AiModelUsage.FALLBACK],
            added_by=_actor(),
        )
        listed = await svc.list_all()
        assert len(listed) == 1
        row: dict[str, Any] = listed[0]
        assert row["api_key_last4"] == "4242"
        assert "api_key_encrypted" not in row
        assert set(row["usages"]) == {"analysis", "fallback"}
        assert row["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_missing_raises_404(self) -> None:
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc.get(PydanticObjectId())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_set_status_disables_model(self) -> None:
        svc = _service()
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-key-0001",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        assert model.id is not None
        updated = await svc.set_status(model.id, AiModelStatus.DISABLED)
        assert updated.status == AiModelStatus.DISABLED

    @pytest.mark.asyncio
    async def test_rotate_key_reencrypts_and_updates_last4(self) -> None:
        svc = _service()
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-original-1111",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        assert model.id is not None
        old_cipher = model.api_key_encrypted
        rotated = await svc.rotate_key(model.id, "sk-rotated-2222")
        assert rotated.api_key_last4 == "2222"
        assert rotated.api_key_encrypted != old_cipher
        assert svc._crypto.decrypt(rotated.api_key_encrypted) == "sk-rotated-2222"

    @pytest.mark.asyncio
    async def test_delete_removes_model(self) -> None:
        svc = _service()
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="sk-key-0002",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        assert model.id is not None
        await svc.delete(model.id)
        with pytest.raises(HTTPException):
            await svc.get(model.id)

    @pytest.mark.asyncio
    async def test_resolve_key_prefers_active_db_model(self) -> None:
        svc = _service(openai_api_key="env-fallback-key")
        await svc.create(
            model_name="gpt-4o-db",
            provider="openai",
            api_key="db-resolved-key",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        resolved = await svc.resolve_key(AiModelUsage.ANALYSIS)
        assert resolved is not None
        provider, model_name, key = resolved
        assert provider == "openai"
        assert model_name == "gpt-4o-db"
        assert key == "db-resolved-key"

    @pytest.mark.asyncio
    async def test_resolve_key_env_fallback_when_no_db_model(self) -> None:
        svc = _service(openai_api_key="env-only-key")
        resolved = await svc.resolve_key(AiModelUsage.RESUME_PARSING)
        assert resolved == ("openai", "gpt-4o-mini", "env-only-key")

    @pytest.mark.asyncio
    async def test_resolve_key_none_when_nothing_configured(self) -> None:
        svc = _service(openai_api_key=None)
        assert await svc.resolve_key(AiModelUsage.ANALYSIS) is None

    @pytest.mark.asyncio
    async def test_resolve_key_falls_through_when_ciphertext_tampered(self) -> None:
        svc = _service(openai_api_key="env-rescue-key")
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="db-key-original",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        # Corrupt the stored ciphertext so decrypt() raises -> env fallback.
        model.api_key_encrypted = "not-valid-base64-ciphertext"
        await model.save()
        resolved = await svc.resolve_key(AiModelUsage.ANALYSIS)
        assert resolved == ("openai", "gpt-4o", "env-rescue-key")

    @pytest.mark.asyncio
    async def test_disabled_db_model_is_skipped_for_env(self) -> None:
        svc = _service(openai_api_key="env-key-here")
        model = await svc.create(
            model_name="gpt-4o",
            provider="openai",
            api_key="db-disabled-key",
            usages=[AiModelUsage.ANALYSIS],
            added_by=_actor(),
        )
        assert model.id is not None
        await svc.set_status(model.id, AiModelStatus.DISABLED)
        resolved = await svc.resolve_key(AiModelUsage.ANALYSIS)
        # Disabled model is not "active", so env fallback wins.
        assert resolved == ("openai", "gpt-4o", "env-key-here")
