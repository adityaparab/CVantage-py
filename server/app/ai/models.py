"""AI model registry service (issue #47).

Manages the ``aimodels`` collection: create, list, disable, rotate keys.
Resolution order per usage type: active DB model -> env fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from fastapi import HTTPException

from app.ai.crypto import CryptoService
from app.config import Settings
from app.database.models import AiModel, AiModelStatus, AiModelUsage


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _mask_key(raw_key: str) -> str:
    """Return last 4 characters of an API key for admin UI display."""
    cleaned = raw_key.strip()
    if len(cleaned) <= 4:
        return "****" + cleaned[-4:] if cleaned else "****"
    return cleaned[-4:]


class AiModelService:
    """CRUD + resolution for AI models with encrypted API keys."""

    def __init__(self, crypto: CryptoService, settings: Settings) -> None:
        self._crypto = crypto
        self._settings = settings

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        model_name: str,
        provider: str,
        api_key: str,
        usages: list[AiModelUsage],
        added_by: PydanticObjectId,
    ) -> AiModel:
        """Create a new AI model entry with an encrypted API key."""
        encrypted = self._crypto.encrypt(api_key)
        model = AiModel(
            model_name=model_name,
            provider=provider,
            api_key_encrypted=encrypted,
            api_key_last4=_mask_key(api_key),
            usages=usages,
            added_by=added_by,
        )
        try:
            await model.insert()
        except Exception:
            raise HTTPException(
                status_code=409,
                detail={"message": f"Model '{provider}/{model_name}' already exists"},
            ) from None
        return model

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all models with masked keys (last 4 chars only)."""
        models = await AiModel.find_all().to_list()
        result: list[dict[str, Any]] = []
        for m in models:
            result.append(
                {
                    "id": str(m.id),
                    "model_name": m.model_name,
                    "provider": m.provider,
                    "api_key_last4": m.api_key_last4,
                    "usages": [u.value for u in m.usages],
                    "status": m.status.value,
                    "added_by": str(m.added_by),
                    "created_at": m.created_at.isoformat(),
                }
            )
        return result

    async def get(self, model_id: PydanticObjectId) -> AiModel:
        model = await AiModel.get(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail={"message": "Model not found"})
        return model

    async def set_status(self, model_id: PydanticObjectId, status: AiModelStatus) -> AiModel:
        model = await self.get(model_id)
        model.status = status
        await model.save()
        return model

    async def rotate_key(self, model_id: PydanticObjectId, new_api_key: str) -> AiModel:
        """Rotate (re-encrypt) the API key for a model."""
        model = await self.get(model_id)
        model.api_key_encrypted = self._crypto.encrypt(new_api_key)
        model.api_key_last4 = _mask_key(new_api_key)
        await model.save()
        return model

    async def delete(self, model_id: PydanticObjectId) -> None:
        model = await self.get(model_id)
        await model.delete()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve_key(self, usage: AiModelUsage) -> tuple[str, str, str] | None:
        """Resolve an API key for *usage*.

        Returns (provider, model_name, decrypted_api_key) or None if
        no model or env fallback is configured.
        """
        # 1. Active DB model for this usage
        model = await AiModel.find_one(
            {
                "status": AiModelStatus.ACTIVE.value,
                "usages": usage.value,
            },
            sort=[("created_at", -1)],
        )
        if model is not None:
            try:
                api_key = self._crypto.decrypt(model.api_key_encrypted)
                return (model.provider, model.model_name, api_key)
            except ValueError:
                pass  # fall through to env

        # 2. Env fallback
        return self._env_fallback(usage)

    def _env_fallback(self, usage: AiModelUsage) -> tuple[str, str, str] | None:
        """Check if OPENAI_API_KEY is configured in env."""
        key = self._settings.openai_api_key
        if key:
            model_map = {
                AiModelUsage.RESUME_PARSING: "gpt-4o-mini",
                AiModelUsage.ANALYSIS: "gpt-4o",
                AiModelUsage.FALLBACK: "gpt-4o-mini",
            }
            return ("openai", model_map.get(usage, "gpt-4o-mini"), key)
        return None
