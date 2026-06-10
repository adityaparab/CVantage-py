"""Notifications service (issue #56).

Manages in-app bell notifications for analysis lifecycle events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from fastapi import HTTPException

from app.database.models import (
    Notification,
    NotificationState,
    NotificationType,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def create_notification(
    user_id: PydanticObjectId,
    analysis_id: PydanticObjectId,
    notif_type: NotificationType,
    title: str,
    body: str | None = None,
) -> Notification:
    """Create a notification, replacing any existing active one for the same analysis.

    The unique partial index on analysis_id + state=active ensures only one active
    notification exists per analysis — a new one replaces the old automatically.
    """
    # Clear any existing active notification for this analysis first
    existing = await Notification.find_one(
        {
            "analysis_id": analysis_id,
            "state": NotificationState.ACTIVE.value,
        }
    )
    if existing is not None:
        existing.state = NotificationState.CLEARED
        existing.cleared_at = _utcnow()
        await existing.save()

    notification = Notification(
        user_id=user_id,
        analysis_id=analysis_id,
        type=notif_type,
        title=title,
        body=body,
    )
    await notification.insert()
    return notification


async def create_analysis_start_notification(
    user_id: PydanticObjectId,
    analysis_id: PydanticObjectId,
    analysis_name: str,
) -> Notification:
    """Create a notification when an analysis starts."""
    return await create_notification(
        user_id=user_id,
        analysis_id=analysis_id,
        notif_type=NotificationType.ANALYSIS_IN_PROGRESS,
        title="Analysis In Progress",
        body=f"Your analysis '{analysis_name}' is being processed.",
    )


async def create_analysis_complete_notification(
    user_id: PydanticObjectId,
    analysis_id: PydanticObjectId,
    analysis_name: str,
) -> Notification:
    """Create a notification when an analysis completes."""
    return await create_notification(
        user_id=user_id,
        analysis_id=analysis_id,
        notif_type=NotificationType.ANALYSIS_COMPLETED,
        title="Analysis Complete",
        body=f"Your analysis '{analysis_name}' has completed. View the results.",
    )


async def create_analysis_failed_notification(
    user_id: PydanticObjectId,
    analysis_id: PydanticObjectId,
    analysis_name: str,
) -> Notification:
    """Create a notification when an analysis fails."""
    return await create_notification(
        user_id=user_id,
        analysis_id=analysis_id,
        notif_type=NotificationType.ANALYSIS_FAILED,
        title="Analysis Failed",
        body=f"Your analysis '{analysis_name}' has failed. You can retry it.",
    )


async def list_active_notifications(
    user_id: PydanticObjectId,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List active notifications for the user, newest first."""
    notifications = await Notification.find(
        {"user_id": user_id, "state": NotificationState.ACTIVE.value},
        sort=[("created_at", SortDirection.DESCENDING)],
        limit=limit,
    ).to_list()

    return [
        {
            "id": str(n.id),
            "type": n.type.value,
            "analysis_id": str(n.analysis_id),
            "title": n.title,
            "body": n.body,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


async def clear_notification(
    notification_id: PydanticObjectId,
    user_id: PydanticObjectId,
) -> None:
    """Mark a notification as cleared."""
    notif = await Notification.find_one(
        {
            "_id": notification_id,
            "user_id": user_id,
        }
    )
    if notif is None:
        raise HTTPException(status_code=404, detail={"message": "Notification not found"})

    notif.state = NotificationState.CLEARED
    notif.cleared_at = _utcnow()
    await notif.save()


async def auto_clear_for_analysis(
    analysis_id: PydanticObjectId,
    user_id: PydanticObjectId,
) -> None:
    """Auto-clear active notifications when a user visits the analysis details page."""
    notif = await Notification.find_one(
        {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "state": NotificationState.ACTIVE.value,
        }
    )
    if notif is not None:
        notif.state = NotificationState.CLEARED
        notif.cleared_at = _utcnow()
        await notif.save()
