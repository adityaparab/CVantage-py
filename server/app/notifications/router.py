"""Notifications API routes (issue #56)."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Path, Query

from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.notifications.schemas import (
    ClearNotificationResponse,
    NotificationItem,
    NotificationListResponse,
)
from app.notifications.service import clear_notification, list_active_notifications
from app.resumes.router import _ensure_user_id

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    summary="List active notifications",
    description="Returns the authenticated user's active (uncleared) notifications, newest first.",
    response_model=NotificationListResponse,
    responses={
        200: {"description": "List of active notifications."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
    },
)
async def get_notifications(
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationListResponse:
    user_id = _ensure_user_id(current_user)
    items = await list_active_notifications(user_id, limit=limit)
    return NotificationListResponse(
        items=[NotificationItem(**item) for item in items],
        total=len(items),
    )


@router.post(
    "/{notification_id}/clear",
    summary="Clear a notification",
    description="Marks a notification as cleared (removed from the bell dropdown).",
    response_model=ClearNotificationResponse,
    responses={
        200: {"description": "Notification cleared."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        404: {"model": ErrorEnvelope, "description": "Notification not found."},
    },
)
async def clear_notification_endpoint(
    notification_id: Annotated[PydanticObjectId, Path(description="The notification's ObjectId")],
    current_user: CurrentUser,
) -> ClearNotificationResponse:
    user_id = _ensure_user_id(current_user)
    await clear_notification(notification_id, user_id)
    return ClearNotificationResponse(status="ok")
