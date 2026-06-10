"""Pydantic schemas for the notifications module (issue #56)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationItem(BaseModel):
    """A single notification for the bell dropdown."""

    id: str
    type: str
    analysis_id: str
    title: str
    body: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f40",
                "type": "analysis_completed",
                "analysis_id": "665c3ef2c9d8f76b6e4f4f30",
                "title": "Analysis Complete",
                "body": "Your resume analysis 'Senior Dev JD Review' has completed.",
                "created_at": "2026-06-10T10:00:00Z",
            }
        }
    )


class NotificationListResponse(BaseModel):
    """List of active notifications."""

    items: list[NotificationItem]
    total: int = Field(ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "665c3ef2c9d8f76b6e4f4f40",
                        "type": "analysis_completed",
                        "analysis_id": "665c3ef2c9d8f76b6e4f4f30",
                        "title": "Analysis Complete",
                        "created_at": "2026-06-10T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )


class ClearNotificationResponse(BaseModel):
    """Response after clearing a notification."""

    status: str = "ok"

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})
