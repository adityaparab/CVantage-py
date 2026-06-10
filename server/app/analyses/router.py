"""Analyses API routes (issue #52, #53)."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId
from beanie.odm.enums import SortDirection
from fastapi import APIRouter, HTTPException, Path, Query

from app.analyses.schemas import (
    AnalysisListItem,
    AnalysisListResponse,
    AnalysisResponse,
    AnalysisStepResponse,
    CreateAnalysisRequest,
)
from app.analyses.service import create_analysis, run_full_pipeline
from app.auth.dependencies import CurrentUser
from app.common.schemas import ErrorEnvelope
from app.database.models import Analysis
from app.resumes.router import _ensure_user_id

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _analysis_to_response(a: Analysis) -> AnalysisResponse:
    return AnalysisResponse(
        id=str(a.id),
        name=a.name,
        resume_id=str(a.resume_id),
        job_description=a.job_description,
        status=a.status.value,
        steps=[
            AnalysisStepResponse(
                key=s.key.value,
                status=s.status.value,
                started_at=s.started_at,
                completed_at=s.completed_at,
                error=s.error,
            )
            for s in a.steps
        ],
        result=a.result.model_dump(by_alias=True) if a.result else None,
        model_used=a.model_used,
        started_at=a.started_at,
        completed_at=a.completed_at,
        error=a.error,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _to_list_item(a: Analysis) -> AnalysisListItem:
    return AnalysisListItem(
        id=str(a.id),
        name=a.name,
        resume_id=str(a.resume_id),
        status=a.status.value,
        model_used=a.model_used,
        created_at=a.created_at,
    )


@router.post(
    "",
    summary="Create a new analysis",
    description=(
        "Create a new job-description-vs-resume analysis. The resume is snapshotted "
        "at creation time. The 3-step pipeline runs asynchronously."
    ),
    response_model=AnalysisResponse,
    status_code=201,
    responses={
        201: {"description": "Analysis created and pipeline started."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        404: {"model": ErrorEnvelope, "description": "Resume not found."},
        422: {"model": ErrorEnvelope, "description": "Validation error."},
    },
)
async def post_analysis(
    payload: CreateAnalysisRequest,
    current_user: CurrentUser,
) -> AnalysisResponse:
    user_id = _ensure_user_id(current_user)
    resume_id = PydanticObjectId(payload.resume_id)

    analysis = await create_analysis(user_id, payload.name, payload.job_description, resume_id)

    # Run pipeline with fake provider (real OpenAI integration comes later)
    from app.ai.llm import FakeLlmProvider

    provider = FakeLlmProvider()
    await run_full_pipeline(analysis, provider)

    refreshed = await Analysis.get(analysis.id)
    assert refreshed is not None
    return _analysis_to_response(refreshed)


@router.get(
    "",
    summary="List user's analyses",
    description="Returns a paginated list of the authenticated user's analyses.",
    response_model=AnalysisListResponse,
    responses={
        200: {"description": "Paginated list of analyses."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
    },
)
async def get_analyses(
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AnalysisListResponse:
    user_id = _ensure_user_id(current_user)
    items = await Analysis.find(
        {"user_id": user_id},
        sort=[("created_at", SortDirection.DESCENDING)],
        skip=skip,
        limit=limit,
    ).to_list()
    total = await Analysis.find({"user_id": user_id}).count()
    return AnalysisListResponse(
        items=[_to_list_item(a) for a in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{analysis_id}",
    summary="Get a single analysis",
    description="Returns the full analysis details including step statuses and results.",
    response_model=AnalysisResponse,
    responses={
        200: {"description": "Analysis details."},
        401: {"model": ErrorEnvelope, "description": "Authentication required."},
        404: {"model": ErrorEnvelope, "description": "Analysis not found."},
    },
)
async def get_analysis_by_id(
    analysis_id: Annotated[PydanticObjectId, Path(description="The analysis's ObjectId")],
    current_user: CurrentUser,
) -> AnalysisResponse:
    user_id = _ensure_user_id(current_user)
    analysis = await Analysis.find_one({"_id": analysis_id, "user_id": user_id})
    if analysis is None:
        raise HTTPException(status_code=404, detail={"message": "Analysis not found"})
    return _analysis_to_response(analysis)
