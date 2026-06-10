"""Admin service (issues #59, #60)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from bson.errors import InvalidId
from fastapi import HTTPException

from app.auth.passwords import hash_password
from app.auth.service import _revoke_user_refresh_family, request_password_reset
from app.config import Settings
from app.database.models import (
    Analysis,
    AuditAction,
    AuditLog,
    Notification,
    NotificationState,
    Resume,
    User,
    UserStatus,
)

_SORTABLE_FIELDS = {"created_at", "last_active_at", "full_name", "email"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_admin_stats() -> dict[str, int]:
    """Return platform-wide statistics.

    Uses count_documents for efficiency (not loading all documents).
    """
    registered_users = await User.find_all().count()
    total_resumes = await Resume.find_all().count()
    total_analyses = await Analysis.find_all().count()

    return {
        "registered_users": registered_users,
        "total_resumes": total_resumes,
        "total_analyses": total_analyses,
    }


# ---------------------------------------------------------------------------
# User management (#60)
# ---------------------------------------------------------------------------


def _user_to_item(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "fullName": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "status": user.status.value,
        "registrationDate": user.created_at,
        "lastActiveAt": user.last_active_at,
        "resumeCount": user.resume_count,
        "analysisCount": user.analysis_count,
    }


def _build_search_query(search: str | None) -> dict[str, Any]:
    if not search:
        return {}
    term = search.strip()
    conditions: list[dict[str, Any]] = [
        {"email": {"$regex": term, "$options": "i"}},
        {"full_name": {"$regex": term, "$options": "i"}},
    ]
    try:
        conditions.append({"_id": PydanticObjectId(term)})
    except (InvalidId, ValueError):
        pass
    return {"$or": conditions}


async def list_users(
    search: str | None,
    skip: int,
    limit: int,
    sort_by: str = "created_at",
    descending: bool = True,
) -> dict[str, Any]:
    """List users for the admin console (search + pagination + sort)."""
    if sort_by not in _SORTABLE_FIELDS:
        sort_by = "created_at"
    direction = SortDirection.DESCENDING if descending else SortDirection.ASCENDING

    query = _build_search_query(search)
    total = await User.find(query).count()
    users = await User.find(query, sort=[(sort_by, direction)], skip=skip, limit=limit).to_list()
    return {
        "items": [_user_to_item(u) for u in users],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


async def get_user_or_404(user_id: PydanticObjectId) -> User:
    user = await User.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"message": "User not found"})
    return user


async def _audit(
    actor_id: PydanticObjectId | None,
    action: AuditAction,
    target_id: PydanticObjectId | None,
    meta: dict[str, Any] | None = None,
    target_type: str = "user",
) -> None:
    await AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta,
    ).insert()


async def update_user(
    user_id: PydanticObjectId,
    actor_id: PydanticObjectId | None,
    full_name: str | None,
    email: str | None,
) -> User:
    """Update a user's name/email with uniqueness enforcement + audit."""
    user = await get_user_or_404(user_id)
    changed: dict[str, Any] = {}

    if full_name is not None and full_name != user.full_name:
        user.full_name = full_name
        changed["full_name"] = True

    if email is not None:
        normalized = email.lower().strip()
        if normalized != user.email:
            existing = await User.find_one(User.email == normalized)
            if existing is not None and existing.id != user.id:
                raise HTTPException(status_code=409, detail={"message": "Email already in use"})
            user.email = normalized
            changed["email"] = True

    if changed:
        await user.save()
        await _audit(actor_id, AuditAction.ADMIN_USER_UPDATE, user_id, {"fields": list(changed)})
    return user


async def reset_user_password(
    user_id: PydanticObjectId,
    actor_id: PydanticObjectId | None,
    new_password: str | None,
    settings: Settings,
) -> str:
    """Reset a user's password — set a temp password or trigger a reset email.

    Returns the method used: ``temp_password`` or ``reset_email``.
    """
    user = await get_user_or_404(user_id)

    if new_password:
        user.password_hash = hash_password(new_password)
        await user.save()
        await _revoke_user_refresh_family(user.id)
        method = "temp_password"
    else:
        await request_password_reset(user.email, settings)
        method = "reset_email"

    await _audit(actor_id, AuditAction.ADMIN_PASSWORD_RESET, user_id, {"method": method})
    return method


async def deactivate_user(
    user_id: PydanticObjectId,
    actor_id: PydanticObjectId,
) -> User:
    """Deactivate a user (revokes all refresh tokens). Admins cannot self-deactivate."""
    if actor_id == user_id:
        raise HTTPException(
            status_code=422, detail={"message": "You cannot deactivate your own account"}
        )
    user = await get_user_or_404(user_id)
    user.status = UserStatus.DEACTIVATED
    user.deactivated_at = _utcnow()
    user.deactivated_by = actor_id
    await user.save()
    await _revoke_user_refresh_family(user.id)
    await _audit(actor_id, AuditAction.ADMIN_USER_DEACTIVATE, user_id)
    return user


async def reactivate_user(
    user_id: PydanticObjectId,
    actor_id: PydanticObjectId,
) -> User:
    """Reactivate a previously deactivated user."""
    user = await get_user_or_404(user_id)
    user.status = UserStatus.ACTIVE
    user.deactivated_at = None
    user.deactivated_by = None
    await user.save()
    await _audit(actor_id, AuditAction.ADMIN_USER_REACTIVATE, user_id)
    return user


# ---------------------------------------------------------------------------
# Privacy-bounded resume administration (#61)
# ---------------------------------------------------------------------------


def _resume_to_metadata(resume: Resume) -> dict[str, Any]:
    """Whitelist resume metadata only — never json_resume or original_text."""
    return {
        "id": str(resume.id),
        "name": resume.name,
        "source": resume.source.value,
        "analysisStatus": resume.analysis_status.value,
        "analysisCount": resume.analysis_count,
        "createdAt": resume.created_at,
        "lastAnalyzedAt": resume.last_analyzed_at,
    }


async def list_user_resumes(user_id: PydanticObjectId) -> dict[str, Any]:
    """List a user's (non-deleted) resumes as metadata only."""
    await get_user_or_404(user_id)
    resumes = await Resume.find(
        {"user_id": user_id, "deleted_at": None},
        sort=[("created_at", SortDirection.DESCENDING)],
    ).to_list()
    return {
        "items": [_resume_to_metadata(r) for r in resumes],
        "total": len(resumes),
    }


async def admin_delete_resume(
    resume_id: PydanticObjectId,
    actor_id: PydanticObjectId | None,
) -> None:
    """Soft-delete a resume and cascade to its analyses + notifications.

    Ordered, idempotent operations (no multi-doc transaction, per D15):
    re-running on an already-deleted resume is a no-op.
    """
    resume = await Resume.get(resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    already_deleted = resume.deleted_at is not None
    now = _utcnow()

    # 1. Cascade soft-delete the resume's still-live analyses (none on a re-run).
    analyses = await Analysis.find({"resume_id": resume_id, "deleted_at": None}).to_list()
    for analysis in analyses:
        analysis.deleted_at = now
        analysis.deleted_by = actor_id
        await analysis.save()

        # 2. Clear any active notifications for that analysis.
        notifs = await Notification.find(
            {"analysis_id": analysis.id, "state": NotificationState.ACTIVE.value}
        ).to_list()
        for notif in notifs:
            notif.state = NotificationState.CLEARED
            notif.cleared_at = now
            await notif.save()

    # 3. Finally, soft-delete the resume itself (skip + don't re-audit on a no-op re-run).
    if not already_deleted:
        resume.deleted_at = now
        resume.deleted_by = actor_id
        await resume.save()
        await _audit(
            actor_id,
            AuditAction.ADMIN_RESUME_DELETE,
            resume_id,
            {"cascaded_analyses": len(analyses)},
            target_type="resume",
        )
