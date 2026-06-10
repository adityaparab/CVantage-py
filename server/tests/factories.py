from __future__ import annotations

from typing import Any


def build_user_payload(*, email: str = "candidate@example.com") -> dict[str, Any]:
    return {
        "email": email,
        "full_name": "Example Candidate",
        "role": "candidate",
    }


def build_resume_payload(*, owner_email: str = "candidate@example.com") -> dict[str, Any]:
    return {
        "owner_email": owner_email,
        "title": "Backend Engineer Resume",
        "json_resume": {"basics": {"name": "Example Candidate"}},
    }


def build_analysis_payload(*, resume_id: str = "resume-1") -> dict[str, Any]:
    return {
        "resume_id": resume_id,
        "status": "pending",
        "steps": [],
    }
