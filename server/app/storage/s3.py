from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.storage.interface import sha256_digest


class S3Storage:
    """Stores files in an S3-compatible object store via ``s3fs``.

    Requires the ``s3fs`` package (optional dependency).
    Falls back to ``botocore`` via ``s3fs`` for all S3 operations.
    """

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key: str | None = None,
        secret_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        import s3fs  # type: ignore[import-untyped]

        self._bucket = bucket
        client_kwargs: dict[str, Any] = {}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        self._fs = s3fs.S3FileSystem(
            key=access_key,
            secret=secret_key,
            client_kwargs=client_kwargs,
            config_kwargs={"region_name": region},
            **kwargs,
        )

    def _s3_path(self, key: str) -> str:
        if ".." in key.split("/"):
            raise ValueError(f"Invalid storage key: {key!r}")
        return f"{self._bucket}/{key}"

    async def put(self, key: str, data: bytes) -> str:
        path = self._s3_path(key)
        with self._fs.open(path, "wb") as f:
            f.write(data)
        return sha256_digest(data)

    async def get(self, key: str) -> bytes:
        path = self._s3_path(key)
        try:
            with self._fs.open(path, "rb") as f:
                result: bytes = f.read()
                return result
        except FileNotFoundError:
            raise FileNotFoundError(f"Storage key not found: {key!r}") from None

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        path = self._s3_path(key)
        try:
            with self._fs.open(path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk
        except FileNotFoundError:
            raise FileNotFoundError(f"Storage key not found: {key!r}") from None

    async def delete(self, key: str) -> None:
        path = self._s3_path(key)
        try:
            self._fs.rm(path)
        except FileNotFoundError:
            pass

    async def stat(self, key: str) -> dict[str, object]:
        path = self._s3_path(key)
        try:
            info = self._fs.info(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Storage key not found: {key!r}") from None

        size = info.get("size", 0)
        return {
            "size_bytes": size,
            "sha256": None,  # S3 does not store SHA-256 natively
        }
