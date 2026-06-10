"""Admin service (issue #59)."""

from __future__ import annotations

from app.database.models import Analysis, Resume, User


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
