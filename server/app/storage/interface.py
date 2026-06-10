from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageService(Protocol):
    """Abstract storage interface — local disk or S3-compatible object store.

    All public methods are async. Implementations must be safe for concurrent use.
    """

    async def put(self, key: str, data: bytes) -> str:
        """Store *data* at *key* and return its SHA-256 hex digest."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve the bytes stored at *key*. Raises ``FileNotFoundError`` if missing."""
        ...

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        """Stream the contents of *key* in chunks. Raises ``FileNotFoundError`` if missing."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object at *key*. No-op if missing."""
        ...

    async def stat(self, key: str) -> dict[str, object]:
        """Return metadata dict with at least ``size_bytes`` and ``sha256`` (or None)."""
        ...


def sha256_digest(data: bytes) -> str:
    """Compute the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()
