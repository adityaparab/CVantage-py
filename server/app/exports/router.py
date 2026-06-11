"""Resume export endpoints (issue #90) — streamed DOCX / PDF download."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.database.models import Resume
from app.exports.docx_export import render_docx
from app.exports.pdf_export import render_pdf
from app.resumes.router import _ensure_user_id

router = APIRouter(prefix="/resumes", tags=["exports"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", name.strip()) or "resume"
    return cleaned[:80]


@router.get(
    "/{resume_id}/export",
    summary="Export a resume as PDF or DOCX",
    description=(
        "Renders the resume's json-resume document to a downloadable file. "
        "Ownership is enforced — a resume the caller does not own returns 404."
    ),
    responses={
        200: {
            "description": "The rendered resume file (streamed download).",
            "content": {
                "application/pdf": {"example": "<binary PDF>"},
                _DOCX_MIME: {"example": "<binary DOCX>"},
                "application/json": {"example": {"status": "ok"}},
            },
        },
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        404: {"model": ErrorEnvelope, "description": "Resume not found."},
        422: {"model": ErrorEnvelope, "description": "Unsupported export format."},
    },
)
async def export_resume(
    resume_id: Annotated[PydanticObjectId, Path(description="The resume's ObjectId")],
    current_user: CurrentUser,
    export_format: Annotated[
        Literal["pdf", "docx"], Query(alias="format", description="pdf | docx")
    ] = "pdf",
) -> StreamingResponse:
    user_id = _ensure_user_id(current_user)
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    json_resume = resume.json_resume.model_dump(exclude_none=True, by_alias=True)
    if export_format == "docx":
        data = render_docx(resume.name, json_resume)
        media_type = _DOCX_MIME
        extension = "docx"
    else:
        data = render_pdf(resume.name, json_resume)
        media_type = "application/pdf"
        extension = "pdf"

    filename = f"{_safe_filename(resume.name)}.{extension}"
    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
