from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles  # type: ignore[import-untyped]

from app.storage.interface import sha256_digest


class LocalDiskStorage:
    """Stores files on the local filesystem under *base_dir*.

    Path-traversal protection: keys containing ``..`` are rejected.
    Data is fsynced after every write for crash safety.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        if ".." in key.split("/") or key.startswith("/"):
            raise ValueError(f"Invalid storage key: {key!r}")
        resolved = (self._base / key).resolve()
        if not str(resolved).startswith(str(self._base)):
            raise ValueError(f"Path traversal detected for key: {key!r}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    async def put(self, key: str, data: bytes) -> str:
        """Store *data* at *key* and return its SHA-256 hex digest."""
        path = self._safe_path(key)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
            await f.flush()  # flush OS buffer
            os.fsync(f.fileno())  # fsync for crash safety
        return sha256_digest(data)

    async def get(self, key: str) -> bytes:
        path = self._safe_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")
        async with aiofiles.open(path, "rb") as f:
            result: bytes = await f.read()
            return result

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        path = self._safe_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(64 * 1024):  # 64 KiB chunks
                yield chunk

    async def delete(self, key: str) -> None:
        path = self._safe_path(key)
        if path.exists():
            path.unlink()

    async def stat(self, key: str) -> dict[str, object]:
        path = self._safe_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key!r}")
        st = path.stat()
        sha256 = sha256_digest(await self.get(key)) if st.st_size > 0 else None
        return {
            "size_bytes": st.st_size,
            "sha256": sha256,
        }
