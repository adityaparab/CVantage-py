"""Analysis pipeline service (issue #52).

Implements the 3-step analysis pipeline:
1. Compare resume vs JD (scores, strengths/weaknesses, skills/gaps)
2. Generate grouped suggestions with field-level proposed values
3. Prepare interview questions with suggested answers
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from beanie import PydanticObjectId
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.ai.llm import LlmProvider
from app.database.models import (
    Analysis,
    AnalysisResult,
    AnalysisStatus,
    InterviewQuestion,
    Resume,
    ResumeAnalysisStatus,
    StepStatus,
    Suggestion,
)
from app.database.models import (
    JsonResume as DbJsonResume,
)

logger = structlog.get_logger("app.analyses")

# ============================================================================
# Pydantic schemas for the LLM structured output
# ============================================================================


class CompareOutput(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    ats_score: int = Field(..., ge=0, le=100)
    project_score: int | None = Field(None, ge=0, le=100)
    strong_points: list[str] = Field(default_factory=list, max_length=10)
    weak_points: list[str] = Field(default_factory=list, max_length=10)
    matching_skills: list[str] = Field(default_factory=list, max_length=30)
    skill_gaps: list[str] = Field(default_factory=list, max_length=30)


class SuggestionItem(BaseModel):
    group: str
    field_ref: str
    title: str
    description: str
    proposed_value: str | None = None


class SuggestionsOutput(BaseModel):
    suggestions: list[SuggestionItem] = Field(default_factory=list, max_length=20)


class InterviewQuestionItem(BaseModel):
    question: str
    suggested_answer: str


class InterviewOutput(BaseModel):
    questions: list[InterviewQuestionItem] = Field(default_factory=list, max_length=15)


COMPARE_PROMPT = """You are an expert resume reviewer. Compare the following resume against the job 
description and provide a detailed analysis.

Output scores on a 0-100 scale:
- overall_score: How well the resume matches the job overall
- ats_score: How well the resume would pass ATS screening
- project_score: How relevant the candidate's projects are (null if none)

List concrete strong points, weak points, matching skills, and skill gaps."""

SUGGESTIONS_PROMPT = """You are a resume optimization expert. Based on the resume and job
description above, suggest concrete improvements.

Group suggestions by type: ats_improvement, skill_emphasis, wording, skill_addition, project.
Each suggestion must include a field_ref pointing to the json-resume field path."""

INTERVIEW_PROMPT = """You are a technical interviewer. Based on the resume and job description,
prepare interview questions that assess the candidate's fit.

Include both technical and behavioral questions
with suggested answers based on the resume content."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def create_analysis(
    user_id: PydanticObjectId,
    name: str,
    job_description: str,
    resume_id: PydanticObjectId,
) -> Analysis:
    """Create a new analysis with a resume snapshot."""
    resume = await Resume.find_one({"_id": resume_id, "user_id": user_id, "deleted_at": None})
    if resume is None:
        raise HTTPException(status_code=404, detail={"message": "Resume not found"})

    analysis = Analysis(
        user_id=user_id,
        resume_id=resume_id,
        name=name.strip(),
        job_description=job_description.strip(),
        resume_snapshot=resume.json_resume,
    )
    await analysis.insert()

    # Update resume rollup
    resume.analysis_status = ResumeAnalysisStatus.IN_PROGRESS
    await resume.save()

    return analysis


async def run_step_compare(
    analysis: Analysis,
    provider: LlmProvider,
    step_index: int = 0,
) -> AnalysisResult:
    """Step 1: Compare resume vs JD."""
    step = analysis.steps[step_index]
    step.status = StepStatus.IN_PROGRESS
    step.started_at = _utcnow()
    await analysis.save()

    try:
        resume_text = _resume_to_text(analysis.resume_snapshot)
        prompt = f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{analysis.job_description}"
        response = await provider.structured_call(COMPARE_PROMPT, prompt, CompareOutput)
        result = AnalysisResult(
            overall_score=response.parsed.overall_score,
            ats_score=response.parsed.ats_score,
            project_score=response.parsed.project_score,
            strong_points=response.parsed.strong_points,
            weak_points=response.parsed.weak_points,
            matching_skills=response.parsed.matching_skills,
            skill_gaps=response.parsed.skill_gaps,
        )
        step.status = StepStatus.COMPLETED
        step.completed_at = _utcnow()
        await analysis.save()
        return result
    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)[:2000]
        step.completed_at = _utcnow()
        await analysis.save()
        raise


async def run_step_suggestions(
    analysis: Analysis,
    provider: LlmProvider,
    step_index: int = 1,
) -> list[Suggestion]:
    """Step 2: Generate suggestions."""
    step = analysis.steps[step_index]
    step.status = StepStatus.IN_PROGRESS
    step.started_at = _utcnow()
    await analysis.save()

    try:
        resume_text = _resume_to_text(analysis.resume_snapshot)
        prompt = f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{analysis.job_description}"
        response = await provider.structured_call(SUGGESTIONS_PROMPT, prompt, SuggestionsOutput)
        suggestions = [
            Suggestion(
                group=s.group,
                field_ref=s.field_ref,
                title=s.title,
                description=s.description,
                proposed_value=s.proposed_value,
            )
            for s in response.parsed.suggestions
        ]
        step.status = StepStatus.COMPLETED
        step.completed_at = _utcnow()
        await analysis.save()
        return suggestions
    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)[:2000]
        step.completed_at = _utcnow()
        await analysis.save()
        raise


async def run_step_interview(
    analysis: Analysis,
    provider: LlmProvider,
    step_index: int = 2,
) -> list[InterviewQuestion]:
    """Step 3: Generate interview questions."""
    step = analysis.steps[step_index]
    step.status = StepStatus.IN_PROGRESS
    step.started_at = _utcnow()
    await analysis.save()

    try:
        resume_text = _resume_to_text(analysis.resume_snapshot)
        prompt = f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{analysis.job_description}"
        response = await provider.structured_call(INTERVIEW_PROMPT, prompt, InterviewOutput)
        questions = [
            InterviewQuestion(question=q.question, suggested_answer=q.suggested_answer)
            for q in response.parsed.questions
        ]
        step.status = StepStatus.COMPLETED
        step.completed_at = _utcnow()
        await analysis.save()
        return questions
    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)[:2000]
        step.completed_at = _utcnow()
        await analysis.save()
        raise


async def run_full_pipeline(
    analysis: Analysis,
    provider: LlmProvider,
) -> None:
    """Run all 3 analysis steps sequentially.

    If a step fails, prior step results are preserved and the analysis
    is marked as failed with the error.
    """
    analysis.started_at = _utcnow()
    await analysis.save()

    result = None
    try:
        result = await run_step_compare(analysis, provider, 0)
        suggestions = await run_step_suggestions(analysis, provider, 1)
        questions = await run_step_interview(analysis, provider, 2)

        if result is not None:
            result.suggestions = suggestions
            result.interview_questions = questions

        analysis.result = result
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = _utcnow()
        await analysis.save()

        # Update resume rollup
        await _update_resume_rollup(analysis.resume_id, ResumeAnalysisStatus.COMPLETED)

    except Exception as e:
        analysis.status = AnalysisStatus.FAILED
        analysis.error = str(e)[:2000]
        analysis.completed_at = _utcnow()
        # Preserve partial result if step 1 completed
        if result is not None:
            analysis.result = result
        await analysis.save()

        await _update_resume_rollup(analysis.resume_id, ResumeAnalysisStatus.FAILED)
        logger.error("analysis.pipeline_failed", analysis_id=str(analysis.id), error=str(e))


async def _update_resume_rollup(
    resume_id: PydanticObjectId,
    status: ResumeAnalysisStatus,
) -> None:
    """Update the resume's analysis rollup fields."""
    resume = await Resume.get(resume_id)
    if resume is None:
        return
    resume.analysis_status = status
    resume.last_analyzed_at = _utcnow()
    resume.analysis_count += 1
    await resume.save()


def _resume_to_text(resume: DbJsonResume) -> str:
    """Convert a JsonResume to a flat text representation for the LLM."""
    parts: list[str] = []
    data = resume.model_dump(exclude_none=True, by_alias=True)

    basics = data.get("basics", {})
    if isinstance(basics, dict):
        parts.append(f"Name: {basics.get('name', '')}")
        parts.append(f"Email: {basics.get('email', '')}")
        parts.append(f"Summary: {basics.get('summary', '')}")

    for key in ("work", "volunteer", "education", "projects"):
        items = data.get(key, []) or []
        if items:
            parts.append(f"\n=== {key.upper()} ===")
            for item in items:
                if isinstance(item, dict):
                    item_str = " | ".join(f"{k}: {v}" for k, v in item.items() if v)
                    if item_str:
                        parts.append(item_str)

    skills = data.get("skills", []) or []
    if skills:
        parts.append("\n=== SKILLS ===")
        for s in skills:
            if isinstance(s, dict):
                parts.append(f"{s.get('name', '')} ({s.get('level', '')})")

    return "\n".join(parts)
