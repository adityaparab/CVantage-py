"""Resume parsing pipeline (issue #51).

Orchestrates the LLM-based extraction of structured json-resume data
from the raw text of uploaded resume files.
"""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import PydanticObjectId
from fastapi import HTTPException
from pydantic import BaseModel

from app.ai.llm import LlmProvider
from app.database.models import (
    JsonResume as DbJsonResume,
)
from app.database.models import (
    Resume,
    ResumeSource,
    UploadParseStatus,
)
from app.resumes.schemas import Resume as SchemasResume
from app.resumes.text_extraction import extract_text

SYSTEM_PROMPT = """You are a resume parser. Extract structured information from the resume text
below and output a valid json-resume JSON object. Follow the schema exactly.

Rules:
1. Output ONLY valid JSON matching the json-resume schema
2. Set fields to null or empty arrays if information is not present
3. Partial dates use format: "YYYY", "YYYY-MM", or "YYYY-MM-DD"
4. Do NOT include fields not in the schema
5. Normalize company names, job titles, and skill names
6. Extract ALL work experience entries, education entries, and skills
7. For dates, try to extract as much detail as possible"""


class ParseProgressEvent(BaseModel):
    """Event emitted during parsing to notify SSE consumers."""

    resume_id: str
    status: str
    model_used: str | None = None
    error: str | None = None
    timestamp: str = ""


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def run_parse_job(
    resume_id: PydanticObjectId,
    provider: LlmProvider,
) -> None:
    """Execute the resume parsing pipeline for a single resume.

    1. Load the resume document
    2. Extract text from the original file (if uploaded)
    3. Call the LLM to parse the text into json-resume structure
    4. Save the result
    """
    resume = await Resume.get(resume_id)
    if resume is None:
        return

    if resume.source != ResumeSource.UPLOADED:
        return

    # Update status to processing
    resume.upload_parse.status = UploadParseStatus.PROCESSING  # type: ignore[union-attr]
    resume.upload_parse.started_at = _utcnow()  # type: ignore[union-attr]
    await resume.save()

    try:
        # Step 1: Extract text from the stored file
        if resume.original_file is None:
            raise ValueError("No original file found for uploaded resume")

        from app.config import get_settings
        from app.storage import LocalDiskStorage

        settings = get_settings()
        storage = LocalDiskStorage(settings.storage_local_dir)

        file_data = await storage.get(resume.original_file.storage_key)
        ext = f".{resume.original_file.file_name.rsplit('.', 1)[-1].lower()}"
        text, _ = await extract_text(file_data, ext)

        # Store extracted text on the resume
        resume.original_text = text
        await resume.save()

        # Step 2: Call LLM to parse into structured json-resume
        response = await provider.structured_call(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"Parse the following resume text into json-resume format:\n\n{text[:100000]}"
            ),
            schema=SchemasResume,
            temperature=0.1,
            timeout_seconds=120,
        )

        # Step 3: Prune and save the result
        from app.resumes.schemas import resume_to_clean_dict

        cleaned = resume_to_clean_dict(response.parsed)
        resume.json_resume = DbJsonResume.model_validate(cleaned)

        resume.upload_parse.status = UploadParseStatus.COMPLETED  # type: ignore[union-attr]
        resume.upload_parse.completed_at = _utcnow()  # type: ignore[union-attr]
        resume.upload_parse.model_used = response.usage.model  # type: ignore[union-attr]

        await resume.save()

    except Exception as e:
        resume.upload_parse.status = UploadParseStatus.FAILED  # type: ignore[union-attr]
        resume.upload_parse.error = str(e)[:2000]  # type: ignore[union-attr]
        resume.upload_parse.completed_at = _utcnow()  # type: ignore[union-attr]
        await resume.save()
        raise


async def reparse_resume(
    resume_id: PydanticObjectId,
    user_id: PydanticObjectId,
    provider: LlmProvider,
) -> dict[str, object]:
    """Re-parse a failed resume. Returns the resume response dict."""
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    if resume.source != ResumeSource.UPLOADED:
        raise HTTPException(
            status_code=422,
            detail={"message": "Only uploaded resumes can be re-parsed"},
        )

    if resume.upload_parse is None or resume.upload_parse.status != UploadParseStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail={"message": "Only failed parses can be retried"},
        )

    # Reset parse status
    resume.upload_parse.status = UploadParseStatus.PENDING
    resume.upload_parse.error = None
    resume.upload_parse.started_at = None
    resume.upload_parse.completed_at = None
    await resume.save()

    # Run the parse job synchronously
    await run_parse_job(resume_id, provider)

    # Return updated resume
    from app.resumes.schemas import Resume as SchemasResume

    return {
        "id": str(resume.id),
        "name": resume.name,
        "source": resume.source.value,
        "json_resume": (
            SchemasResume.model_validate(
                resume.json_resume.model_dump(exclude_none=True, by_alias=True)
            ).model_dump(by_alias=True)
            if resume.json_resume
            else {}
        ),
        "upload_parse": {
            "status": resume.upload_parse.status.value,
            "model_used": resume.upload_parse.model_used,
            "error": resume.upload_parse.error,
        },
    }
