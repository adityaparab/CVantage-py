from __future__ import annotations

import hashlib
from pathlib import Path as FsPath
from typing import Annotated

import filetype  # type: ignore[import-untyped]
from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi import Path as FAPath

import app.resumes.service as service
from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.config import Settings, get_settings
from app.database.models import (
    ALLOWED_RESUME_MIME,
    MAX_RESUME_FILE_BYTES,
    Resume,
    ResumeSource,
    UploadParse,
    UploadParseStatus,
    User,
)
from app.database.models import (
    JsonResume as DbJsonResume,
)
from app.resumes.schemas import (
    CreateResumeRequest,
    DeleteResumeResponse,
    ResumeListResponse,
    ResumeResponse,
    UpdateResumeRequest,
)
from app.resumes.schemas import Resume as SchemasResume

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
    resume_id: Annotated[PydanticObjectId, FAPath(description="The resume's ObjectId")],
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
    resume_id: Annotated[PydanticObjectId, FAPath(description="The resume's ObjectId")],
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
    resume_id: Annotated[PydanticObjectId, FAPath(description="The resume's ObjectId")],
    current_user: CurrentUser,
) -> DeleteResumeResponse:
    user_id = _ensure_user_id(current_user)
    await service.delete_resume(user_id, resume_id, deleted_by=user_id)
    return DeleteResumeResponse(status="ok")


# ============================================================================
# Upload endpoint (Issue #44)
# ============================================================================

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}


def _validate_upload(upload: UploadFile, data: bytes) -> None:
    """Validate file size, extension, MIME type, and magic bytes."""
    if len(data) > MAX_RESUME_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "message": (
                    f"File too large. Maximum size is {MAX_RESUME_FILE_BYTES // (1024 * 1024)} MB"
                )
            },
        )

    original_filename = (upload.filename or "").strip()
    if not original_filename:
        raise HTTPException(status_code=422, detail={"message": "No filename provided"})

    ext = FsPath(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid file extension '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            },
        )

    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_RESUME_MIME:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid MIME type '{content_type}'. "
                "Only PDF, DOC, and DOCX files are allowed"
            },
        )

    kind = filetype.guess(data)
    detected_mime = kind.mime if kind else ""
    # DOCX/DOC files are ZIP/OLE2-based; filetype detects them as application/zip or similar
    _MAGIC_ALLOWED = set(ALLOWED_RESUME_MIME) | {"application/zip", "application/x-tika-ooxml"}
    if detected_mime not in _MAGIC_ALLOWED:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "File content does not match the expected format. "
                f"Detected type: {detected_mime or 'unknown'}"
            },
        )


def _deduplicate_name(base_name: str, existing_names: set[str]) -> str:
    """Append a numeric suffix if the name already exists."""
    if base_name not in existing_names:
        return base_name
    stem = FsPath(base_name).stem
    ext = FsPath(base_name).suffix
    counter = 1
    while f"{stem} ({counter}){ext}" in existing_names:
        counter += 1
    return f"{stem} ({counter}){ext}"


@router.post(
    "/upload",
    summary="Upload a resume file",
    description=(
        "Upload a PDF, DOC, or DOCX resume file (max 10 MB). "
        "The file is validated for size, extension, MIME type, and magic bytes. "
        "On success, the file is stored via StorageService and a Resume document "
        "is created with source=uploaded and uploadParse=pending. "
        "Use the returned resume id and parse status URL to track AI parsing progress."
    ),
    response_model=ResumeResponse,
    status_code=201,
    responses={
        201: {
            "description": "File uploaded and resume created.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "resume.pdf",
                        "source": "uploaded",
                        "json_resume": {},
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
        413: {
            "model": ErrorEnvelope,
            "description": "File exceeds maximum size.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 413,
                        "error": "Request Entity Too Large",
                        "message": "File too large. Maximum size is 10 MB",
                        "path": "/api/v1/resumes/upload",
                    }
                }
            },
        },
        422: {
            "model": ErrorEnvelope,
            "description": "Validation error (invalid extension, MIME, or magic bytes).",
        },
        429: {
            "model": ErrorEnvelope,
            "description": "Rate limit exceeded for uploads.",
        },
    },
)
async def upload_resume(
    upload: UploadFile,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeResponse:
    """Upload a resume file, validate it, and create a Resume document."""
    data = await upload.read()
    _validate_upload(upload, data)
    user_id = _ensure_user_id(current_user)

    from app.storage import LocalDiskStorage

    storage = LocalDiskStorage(settings.storage_local_dir)

    sha256 = hashlib.sha256(data).hexdigest()
    storage_key = f"{user_id}/{sha256[:16]}/{upload.filename}"

    await storage.put(storage_key, data)

    name = upload.filename or "resume"
    existing = await Resume.find({"user_id": user_id, "deleted_at": None}).to_list()
    existing_names = {r.name for r in existing}
    name = _deduplicate_name(name, existing_names)

    resume = Resume(
        user_id=user_id,
        name=name,
        source=ResumeSource.UPLOADED,
        json_resume=DbJsonResume.model_validate({}),
        original_file={
            "file_name": upload.filename,
            "mime_type": upload.content_type or "application/octet-stream",
            "size_bytes": len(data),
            "storage_key": storage_key,
            "sha256": sha256,
        },
        upload_parse=UploadParse(status=UploadParseStatus.PENDING),
    )
    await resume.insert()

    await User.find({"_id": user_id}).inc({"resume_count": 1})

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
