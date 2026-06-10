"""Service-layer tests for the 3-step analysis pipeline (issues #52/#53, consolidated in #55).

Exercises ``app.analyses.service`` end-to-end against an in-memory Beanie client
with the deterministic ``FakeLlmProvider``: pipeline success/failure, retry,
cancel, and suggestion apply/dismiss (including deep array paths).
"""

from __future__ import annotations

from typing import Any

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.ai.llm import FakeLlmProvider, LlmError, LlmProvider, LlmResponse, LlmUsage
from app.analyses import service as analyses_service
from app.analyses.service import (
    apply_suggestion,
    cancel_analysis,
    create_analysis,
    dismiss_suggestion,
    retry_analysis,
    run_full_pipeline,
)
from app.database.models import (
    Analysis,
    AnalysisStatus,
    JsonResume,
    Notification,
    NotificationState,
    NotificationType,
    Resume,
    ResumeAnalysisStatus,
    ResumeSource,
    StepStatus,
)

_COMPARE_FIXTURE = {
    "overall_score": 82,
    "ats_score": 75,
    "project_score": 68,
    "strong_points": ["Strong Python background"],
    "weak_points": ["Limited cloud experience"],
    "matching_skills": ["python", "fastapi"],
    "skill_gaps": ["kubernetes"],
}
_SUGGESTIONS_FIXTURE = {
    "suggestions": [
        {
            "group": "wording",
            "field_ref": "basics.summary",
            "title": "Sharpen the summary",
            "description": "Lead with impact metrics.",
            "proposed_value": "Senior engineer with 8y building resilient APIs.",
        },
        {
            "group": "skill_emphasis",
            "field_ref": "work[0].position",
            "title": "Clarify title",
            "description": "Use the canonical title.",
            "proposed_value": "Staff Software Engineer",
        },
    ]
}
_INTERVIEW_FIXTURE = {
    "questions": [
        {"question": "Describe a hard scaling problem.", "suggested_answer": "Sharded the DB."},
    ]
}


def _fake_provider() -> FakeLlmProvider:
    provider = FakeLlmProvider()
    provider.register("CompareOutput", _COMPARE_FIXTURE)
    provider.register("SuggestionsOutput", _SUGGESTIONS_FIXTURE)
    provider.register("InterviewOutput", _INTERVIEW_FIXTURE)
    return provider


class _FailOnSchema(LlmProvider):
    """Wraps the fake provider but raises when a given schema is requested."""

    def __init__(self, fail_schema: str) -> None:
        self._fail_schema = fail_schema
        self._base = _fake_provider()

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[Any],
        model_name: str = "",
        temperature: float = 0.0,
        timeout_seconds: int = 60,
    ) -> LlmResponse[Any]:
        if schema.__name__ == self._fail_schema:
            raise LlmError("step failed", "test")
        return await self._base.structured_call(
            system_prompt, user_prompt, schema, model_name, temperature, timeout_seconds
        )


async def _make_resume(json_resume: dict[str, Any] | None = None) -> Resume:
    resume = Resume(
        user_id=PydanticObjectId(),
        name="Backend Engineer Resume",
        source=ResumeSource.CREATED,
        json_resume=JsonResume.model_validate(
            json_resume
            or {
                "basics": {"name": "Ada Lovelace", "summary": "Engineer."},
                "work": [{"name": "Acme", "position": "Engineer", "summary": "Built things."}],
                "skills": [{"name": "python", "level": "expert"}],
            }
        ),
    )
    await resume.insert()
    return resume


@pytest.mark.usefixtures("beanie_db")
class TestCreateAndRunPipeline:
    @pytest.mark.asyncio
    async def test_create_analysis_snapshots_resume(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD Review",
            job_description="x" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        assert analysis.status == AnalysisStatus.PENDING
        assert analysis.resume_snapshot.basics is not None
        assert analysis.resume_snapshot.basics.name == "Ada Lovelace"
        # Resume rollup flipped to in-progress.
        reloaded = await Resume.get(resume.id)
        assert reloaded is not None
        assert reloaded.analysis_status == ResumeAnalysisStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_create_analysis_missing_resume_404(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await create_analysis(
                user_id=PydanticObjectId(),
                name="JD Review",
                job_description="x" * 60,
                resume_id=PydanticObjectId(),
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_full_pipeline_completes_all_steps(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD Review",
            job_description="Looking for a senior backend engineer. " * 5,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        await run_full_pipeline(analysis, _fake_provider())

        done = await Analysis.get(analysis.id)
        assert done is not None
        assert done.status == AnalysisStatus.COMPLETED
        assert all(s.status == StepStatus.COMPLETED for s in done.steps)
        assert done.result is not None
        assert done.result.overall_score == 82
        assert len(done.result.suggestions) == 2
        assert len(done.result.interview_questions) == 1

        # Resume rollup completed + counter incremented.
        reloaded = await Resume.get(resume.id)
        assert reloaded is not None
        assert reloaded.analysis_status == ResumeAnalysisStatus.COMPLETED
        assert reloaded.analysis_count == 1

        # A completion notification exists and is active.
        notif = await Notification.find_one(
            {"analysis_id": analysis.id, "state": NotificationState.ACTIVE.value}
        )
        assert notif is not None
        assert notif.type == NotificationType.ANALYSIS_COMPLETED

    @pytest.mark.asyncio
    async def test_pipeline_failure_preserves_prior_step_and_retries(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD Review",
            job_description="y" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        # Fail on the suggestions (2nd) step.
        await run_full_pipeline(analysis, _FailOnSchema("SuggestionsOutput"))

        failed = await Analysis.get(analysis.id)
        assert failed is not None
        assert failed.status == AnalysisStatus.FAILED
        assert failed.steps[0].status == StepStatus.COMPLETED  # compare survived
        assert failed.steps[1].status == StepStatus.FAILED
        # Partial compare result was preserved.
        assert failed.result is not None
        assert failed.result.overall_score == 82

        # Failure notification raised.
        notif = await Notification.find_one(
            {"analysis_id": analysis.id, "state": NotificationState.ACTIVE.value}
        )
        assert notif is not None
        assert notif.type == NotificationType.ANALYSIS_FAILED

        # Retry with a healthy provider completes it.
        recovered = await retry_analysis(analysis.id, resume.user_id, _fake_provider())  # type: ignore[arg-type]
        assert recovered.status == AnalysisStatus.COMPLETED
        assert recovered.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD",
            job_description="z" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        with pytest.raises(HTTPException) as exc:
            await retry_analysis(analysis.id, resume.user_id, _fake_provider())  # type: ignore[arg-type]
        assert exc.value.status_code == 422


@pytest.mark.usefixtures("beanie_db")
class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_pending(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD",
            job_description="q" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        cancelled = await cancel_analysis(analysis.id, resume.user_id)  # type: ignore[arg-type]
        assert cancelled.status == AnalysisStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_non_pending_422(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD",
            job_description="q" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        await run_full_pipeline(analysis, _fake_provider())
        with pytest.raises(HTTPException) as exc:
            await cancel_analysis(analysis.id, resume.user_id)  # type: ignore[arg-type]
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_missing_404(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await cancel_analysis(PydanticObjectId(), PydanticObjectId())
        assert exc.value.status_code == 404


@pytest.mark.usefixtures("beanie_db")
class TestSuggestionApplyDismiss:
    async def _completed(self) -> tuple[Analysis, Resume]:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD",
            job_description="w" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        await run_full_pipeline(analysis, _fake_provider())
        done = await Analysis.get(analysis.id)
        assert done is not None
        return done, resume

    @pytest.mark.asyncio
    async def test_apply_simple_path_mutates_resume(self) -> None:
        analysis, resume = await self._completed()
        assert analysis.result is not None
        sug = analysis.result.suggestions[0]  # basics.summary
        await apply_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]

        reloaded = await Resume.get(resume.id)
        assert reloaded is not None
        assert reloaded.json_resume.basics is not None
        assert (
            reloaded.json_resume.basics.summary
            == "Senior engineer with 8y building resilient APIs."
        )

    @pytest.mark.asyncio
    async def test_apply_array_path_mutates_resume(self) -> None:
        analysis, resume = await self._completed()
        assert analysis.result is not None
        sug = analysis.result.suggestions[1]  # work[0].position
        await apply_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]

        reloaded = await Resume.get(resume.id)
        assert reloaded is not None
        assert reloaded.json_resume.work is not None
        assert reloaded.json_resume.work[0].position == "Staff Software Engineer"

    @pytest.mark.asyncio
    async def test_apply_twice_is_rejected(self) -> None:
        analysis, resume = await self._completed()
        assert analysis.result is not None
        sug = analysis.result.suggestions[0]
        await apply_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]
        with pytest.raises(HTTPException) as exc:
            await apply_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_apply_unknown_suggestion_404(self) -> None:
        analysis, resume = await self._completed()
        with pytest.raises(HTTPException) as exc:
            await apply_suggestion(analysis.id, resume.user_id, PydanticObjectId())  # type: ignore[arg-type]
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_apply_on_deleted_resume_410(self) -> None:
        analysis, resume = await self._completed()
        assert analysis.result is not None
        # Soft-delete the resume. Re-fetch first: the pipeline bumped the
        # resume's revision via a separate instance, so the one returned by
        # the helper is stale.
        from datetime import UTC, datetime

        fresh = await Resume.get(resume.id)
        assert fresh is not None
        fresh.deleted_at = datetime.now(UTC)
        await fresh.save()
        sug = analysis.result.suggestions[0]
        with pytest.raises(HTTPException) as exc:
            await apply_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]
        assert exc.value.status_code == 410

    @pytest.mark.asyncio
    async def test_dismiss_marks_suggestion(self) -> None:
        analysis, resume = await self._completed()
        assert analysis.result is not None
        sug = analysis.result.suggestions[0]
        result = await dismiss_suggestion(analysis.id, resume.user_id, sug.suggestion_id)  # type: ignore[arg-type]
        assert result["action"] == "dismissed"

        reloaded = await Analysis.get(analysis.id)
        assert reloaded is not None
        assert reloaded.result is not None
        assert reloaded.result.suggestions[0].dismissed is True


class _UsageProvider(LlmProvider):
    """Fake provider that reports fixed token usage per call."""

    def __init__(self, prompt: int, completion: int) -> None:
        self._base = _fake_provider()
        self._prompt = prompt
        self._completion = completion

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[Any],
        model_name: str = "",
        temperature: float = 0.0,
        timeout_seconds: int = 60,
    ) -> LlmResponse[Any]:
        resp = await self._base.structured_call(
            system_prompt, user_prompt, schema, model_name, temperature, timeout_seconds
        )
        resp.usage = LlmUsage(
            prompt_tokens=self._prompt,
            completion_tokens=self._completion,
            total_tokens=self._prompt + self._completion,
        )
        return resp


@pytest.mark.usefixtures("beanie_db")
class TestCostGuards:
    @pytest.mark.asyncio
    async def test_token_usage_accumulated_across_steps(self) -> None:
        resume = await _make_resume()
        analysis = await create_analysis(
            user_id=resume.user_id,
            name="JD",
            job_description="u" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        await run_full_pipeline(analysis, _UsageProvider(prompt=100, completion=25))

        done = await Analysis.get(analysis.id)
        assert done is not None
        assert done.token_usage is not None
        # Three steps, each 100 prompt + 25 completion.
        assert done.token_usage.prompt_tokens == 300
        assert done.token_usage.completion_tokens == 75
        assert done.token_usage.total_tokens == 375

    @pytest.mark.asyncio
    async def test_concurrent_analysis_limit_returns_429(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import Settings

        monkeypatch.setattr(
            analyses_service,
            "get_settings",
            lambda: Settings(environment="test", max_concurrent_analyses_per_user=1),
        )
        resume = await _make_resume()
        # First analysis (pending) consumes the single slot.
        await create_analysis(
            user_id=resume.user_id,
            name="A1",
            job_description="a" * 60,
            resume_id=resume.id,  # type: ignore[arg-type]
        )
        with pytest.raises(HTTPException) as exc:
            await create_analysis(
                user_id=resume.user_id,
                name="A2",
                job_description="b" * 60,
                resume_id=resume.id,  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 429


class TestDeepPathAndText:
    def test_set_deep_path_invalid_ref_raises(self) -> None:
        resume = JsonResume.model_validate({"basics": {"name": "X"}})
        with pytest.raises(ValueError):
            analyses_service._set_deep_path(resume, "work[0].position", "nope")

    def test_resume_to_text_includes_sections(self) -> None:
        resume = JsonResume.model_validate(
            {
                "basics": {"name": "Ada", "email": "ada@x.io", "summary": "Hi"},
                "work": [{"name": "Acme", "position": "Eng"}],
                "skills": [{"name": "python", "level": "expert"}],
            }
        )
        text = analyses_service._resume_to_text(resume)
        assert "Ada" in text
        assert "SKILLS" in text
        assert "python" in text
