from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Path, Query

import app.resumes.service as service
from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.resumes.schemas import (
    CreateResumeRequest,
    DeleteResumeResponse,
    ResumeListResponse,
    ResumeResponse,
    UpdateResumeRequest,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _ensure_user_id(current_user: CurrentUser) -> PydanticObjectId:
    """Extract the user id, raising 401 if somehow missing."""
    uid = current_user.id
    if uid is None:
        raise HTTPException(status_code=401, detail={"message": "Authentication required"})
    return uid


@router.post(
    "",
    summary="Create a new resume",
    description=(
        "Create a new form-created resume from a json-resume document. "
        "Placeholder fields are automatically pruned before storage. "
        "Returns the created resume with generated id and timestamps."
    ),
    response_model=ResumeResponse,
    status_code=201,
    responses={
        201: {
            "description": "Resume created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "Software Engineer Resume",
                        "source": "created",
                        "json_resume": {"basics": {"name": "Jane Doe"}},
                        "analysis_status": "unanalyzed",
                        "original_text": None,
                        "last_analyzed_at": None,
                        "analysis_count": 0,
                        "created_at": "2026-06-10T10:00:00Z",
                        "updated_at": "2026-06-10T10:00:00Z",
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 401,
                        "error": "Unauthorized",
                        "message": "Authentication required",
                        "path": "/api/v1/resumes",
                    }
                }
            },
        },
        409: {
            "model": ErrorEnvelope,
            "description": "A resume with this name already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 409,
                        "error": "Conflict",
                        "message": "A resume with this name already exists",
                        "path": "/api/v1/resumes",
                    }
                }
            },
        },
        422: {
            "model": ErrorEnvelope,
            "description": "Validation error in request body.",
        },
    },
)
async def post_resume(
    payload: CreateResumeRequest,
    current_user: CurrentUser,
) -> ResumeResponse:
    user_id = _ensure_user_id(current_user)
    return await service.create_resume(user_id, payload)


@router.get(
    "",
    summary="List user's resumes",
    description=(
        "Returns a paginated list of the authenticated user's non-deleted resumes, "
        "sorted by creation date (newest first by default). "
        "Supports cursor/offset pagination via skip and limit query params."
    ),
    response_model=ResumeListResponse,
    responses={
        200: {
            "description": "Paginated list of resumes.",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "665c3ef2c9d8f76b6e4f4f20",
                                "name": "Software Engineer Resume",
                                "source": "created",
                                "analysis_status": "unanalyzed",
                                "last_analyzed_at": None,
                                "analysis_count": 0,
                                "created_at": "2026-06-10T10:00:00Z",
                            }
                        ],
                        "total": 1,
                        "skip": 0,
                        "limit": 20,
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
    },
)
async def get_resumes(
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0, examples=[0])] = 0,
    limit: Annotated[int, Query(ge=1, le=100, examples=[20])] = 20,
    sort_field: Annotated[str, Query(examples=["created_at"])] = "created_at",
    sort_desc: Annotated[bool, Query(examples=[True])] = True,
) -> ResumeListResponse:
    user_id = _ensure_user_id(current_user)
    return await service.list_resumes(
        user_id,
        skip=skip,
        limit=limit,
        sort_field=sort_field,
        sort_desc=sort_desc,
    )


@router.get(
    "/{resume_id}",
    summary="Get a single resume",
    description=(
        "Returns the full resume document including the json-resume payload. "
        "Ownership is enforced — requesting another user's resume returns 404."
    ),
    response_model=ResumeResponse,
    responses={
        200: {
            "description": "Resume found.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "Software Engineer Resume",
                        "source": "created",
                        "json_resume": {"basics": {"name": "Jane Doe"}},
                        "analysis_status": "unanalyzed",
                        "original_text": None,
                        "last_analyzed_at": None,
                        "analysis_count": 0,
                        "created_at": "2026-06-10T10:00:00Z",
                        "updated_at": "2026-06-10T10:00:00Z",
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
        404: {
            "model": ErrorEnvelope,
            "description": "Resume not found (or owned by another user).",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 404,
                        "error": "Not Found",
                        "message": "Resume not found",
                        "path": "/api/v1/resumes/665c3ef2c9d8f76b6e4f4f20",
                    }
                }
            },
        },
    },
)
async def get_resume_by_id(
    resume_id: Annotated[PydanticObjectId, Path(description="The resume's ObjectId")],
    current_user: CurrentUser,
) -> ResumeResponse:
    user_id = _ensure_user_id(current_user)
    return await service.get_resume(user_id, resume_id)


@router.patch(
    "/{resume_id}",
    summary="Update a resume",
    description=(
        "Update the name and/or json-resume document of an existing resume. "
        "Uses Beanie revision-based optimistic concurrency — a version conflict "
        "returns 409. Placeholder fields are automatically pruned before storage."
    ),
    response_model=ResumeResponse,
    responses={
        200: {
            "description": "Resume updated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "Senior Engineer Resume",
                        "source": "created",
                        "json_resume": {"basics": {"name": "Jane Doe"}},
                        "analysis_status": "unanalyzed",
                        "original_text": None,
                        "last_analyzed_at": None,
                        "analysis_count": 0,
                        "created_at": "2026-06-10T10:00:00Z",
                        "updated_at": "2026-06-10T10:30:00Z",
                    }
                }
            },
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
        404: {
            "model": ErrorEnvelope,
            "description": "Resume not found.",
        },
        409: {
            "model": ErrorEnvelope,
            "description": "Version conflict (optimistic concurrency) or name conflict.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 409,
                        "error": "Conflict",
                        "message": "A resume with this name already exists",
                        "path": "/api/v1/resumes/665c3ef2c9d8f76b6e4f4f20",
                    }
                }
            },
        },
        422: {
            "model": ErrorEnvelope,
            "description": "Validation error in request body.",
        },
    },
)
async def patch_resume(
    resume_id: Annotated[PydanticObjectId, Path(description="The resume's ObjectId")],
    payload: UpdateResumeRequest,
    current_user: CurrentUser,
) -> ResumeResponse:
    user_id = _ensure_user_id(current_user)
    return await service.update_resume(user_id, resume_id, payload)


@router.delete(
    "/{resume_id}",
    summary="Delete a resume (soft)",
    description=(
        "Soft-deletes a resume by setting the deleted_at timestamp. "
        "The resume is excluded from all queries. Ownership is enforced. "
        "An audit log entry is created for the deletion."
    ),
    response_model=DeleteResumeResponse,
    responses={
        200: {
            "description": "Resume soft-deleted successfully.",
            "content": {"application/json": {"example": {"status": "ok"}}},
        },
        401: {
            "model": ErrorEnvelope,
            "description": "Missing or invalid bearer token.",
        },
        404: {
            "model": ErrorEnvelope,
            "description": "Resume not found.",
        },
    },
)
async def delete_resume_by_id(
    resume_id: Annotated[PydanticObjectId, Path(description="The resume's ObjectId")],
    current_user: CurrentUser,
) -> DeleteResumeResponse:
    user_id = _ensure_user_id(current_user)
    await service.delete_resume(user_id, resume_id, deleted_by=user_id)
    return DeleteResumeResponse(status="ok")
