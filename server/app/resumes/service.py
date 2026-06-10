from __future__ import annotations

from datetime import UTC, datetime

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.database.models import (
    AuditAction,
    AuditLog,
    Resume,
    ResumeSource,
)
from app.database.models import (
    JsonResume as DbJsonResume,
)
from app.resumes.schemas import (
    CreateResumeRequest,
    ResumeListItem,
    ResumeListResponse,
    ResumeResponse,
    UpdateResumeRequest,
    resume_to_clean_dict,
)
from app.resumes.schemas import (
    Resume as SchemasResume,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_resume_response(resume: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=str(resume.id),
        name=resume.name,
        source=resume.source.value,
        json_resume=SchemasResume.model_validate(
            resume.json_resume.model_dump(exclude_none=True, by_alias=True)
        ),
        analysis_status=resume.analysis_status.value,
        original_text=resume.original_text,
        last_analyzed_at=resume.last_analyzed_at,
        analysis_count=resume.analysis_count,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


def _to_resume_list_item(resume: Resume) -> ResumeListItem:
    return ResumeListItem(
        id=str(resume.id),
        name=resume.name,
        source=resume.source.value,
        analysis_status=resume.analysis_status.value,
        last_analyzed_at=resume.last_analyzed_at,
        analysis_count=resume.analysis_count,
        created_at=resume.created_at,
    )


async def create_resume(
    user_id: PydanticObjectId,
    payload: CreateResumeRequest,
) -> ResumeResponse:
    """Create a new form-created resume with placeholder pruning."""
    json_resume_dict = resume_to_clean_dict(payload.json_resume)

    resume = Resume(
        user_id=user_id,
        name=payload.name.strip(),
        source=ResumeSource.CREATED,
        json_resume=DbJsonResume.model_validate(json_resume_dict),
    )

    try:
        await resume.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail={"message": "A resume with this name already exists"},
        ) from None

    return _to_resume_response(resume)


async def list_resumes(
    user_id: PydanticObjectId,
    *,
    skip: int = 0,
    limit: int = 20,
    sort_field: str = "created_at",
    sort_desc: bool = True,
) -> ResumeListResponse:
    """List non-deleted resumes for the current user, newest first."""
    sort_dir = SortDirection.DESCENDING if sort_desc else SortDirection.ASCENDING
    sort_key = sort_field if sort_field in ("created_at", "updated_at", "name") else "created_at"

    query = Resume.find(
        {"user_id": user_id, "deleted_at": None},
        sort=[(sort_key, sort_dir)],
        skip=skip,
        limit=limit,
    )
    items = await query.to_list()
    total = await Resume.find({"user_id": user_id, "deleted_at": None}).count()

    return ResumeListResponse(
        items=[_to_resume_list_item(r) for r in items],
        total=total,
        skip=skip,
        limit=limit,
    )


async def get_resume(
    user_id: PydanticObjectId,
    resume_id: PydanticObjectId,
) -> ResumeResponse:
    """Get a single resume by ID. Ownership enforced — foreign id returns 404."""
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    return _to_resume_response(resume)


async def update_resume(
    user_id: PydanticObjectId,
    resume_id: PydanticObjectId,
    payload: UpdateResumeRequest,
) -> ResumeResponse:
    """Update resume name and/or json_resume with optimistic concurrency."""
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    if payload.name is not None:
        resume.name = payload.name.strip()

    if payload.json_resume is not None:
        cleaned = resume_to_clean_dict(payload.json_resume)
        resume.json_resume = DbJsonResume.model_validate(cleaned)

    try:
        await resume.save()
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail={"message": "A resume with this name already exists"},
        ) from None

    return _to_resume_response(resume)


async def delete_resume(
    user_id: PydanticObjectId,
    resume_id: PydanticObjectId,
    *,
    deleted_by: PydanticObjectId | None = None,
) -> None:
    """Soft-delete a resume. Ownership enforced — foreign id returns 404."""
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    now = _utcnow()
    resume.deleted_at = now
    resume.deleted_by = deleted_by or user_id
    await resume.save()

    # Audit log
    await AuditLog(
        actor_id=deleted_by or user_id,
        action=AuditAction.RESUME_DELETE,
        target_type="resume",
        target_id=resume.id,
        meta={"resume_name": resume.name, "source": resume.source.value},
    ).insert()
