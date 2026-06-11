"""Single-server SPA serving (issue #92).

When ``frontend/dist`` exists, the FastAPI app serves it on the same port as the
API: hashed assets are immutable-cached, ``index.html`` is no-cache, and any
non-``/api`` path falls back to ``index.html`` so client-side deep links work.
Unknown ``/api/**`` paths still return the JSON error envelope (never the SPA).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
_NO_CACHE = {"Cache-Control": "no-cache"}


def mount_spa(app: FastAPI, dist_dir: Path) -> bool:
    """Mount the built SPA if ``dist_dir`` exists. Returns whether it was mounted."""
    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        return False

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Never let the SPA shadow the API surface — unknown API paths are JSON 404s.
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail={"message": "Not found"})

        candidate = (dist_dir / full_path).resolve()
        # Serve a real static file (favicon, hashed asset) if it is inside dist.
        if full_path and candidate.is_file() and dist_dir.resolve() in candidate.parents:
            headers = _IMMUTABLE if full_path.startswith("assets/") else _NO_CACHE
            return FileResponse(candidate, headers=headers)

        # Otherwise return the SPA shell so client-side routing can take over.
        return FileResponse(index_file, headers=_NO_CACHE)

    return True
