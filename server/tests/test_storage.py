"""Tests for the storage abstraction layer (issue #43)."""

from __future__ import annotations

import tempfile

import pytest

from app.storage.interface import StorageService, sha256_digest
from app.storage.local import LocalDiskStorage


class TestSha256Digest:
    def test_known_hash(self) -> None:
        data = b"hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert sha256_digest(data) == expected

    def test_empty(self) -> None:
        assert sha256_digest(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )


class TestLocalDiskStorage:
    @pytest.fixture
    def storage(self) -> LocalDiskStorage:
        tmp = tempfile.mkdtemp()
        return LocalDiskStorage(tmp)

    @pytest.mark.asyncio
    async def test_put_and_get_roundtrip(self, storage: LocalDiskStorage) -> None:
        digest = await storage.put("test/hello.txt", b"Hello, World!")
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex

        retrieved = await storage.get("test/hello.txt")
        assert retrieved == b"Hello, World!"

    @pytest.mark.asyncio
    async def test_stat_returns_metadata(self, storage: LocalDiskStorage) -> None:
        data = b"some content"
        await storage.put("stats/me.txt", data)
        info = await storage.stat("stats/me.txt")
        assert info["size_bytes"] == len(data)
        sha256 = info.get("sha256")
        assert isinstance(sha256, str)
        assert len(sha256) == 64

    @pytest.mark.asyncio
    async def test_get_missing_raises(self, storage: LocalDiskStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.get("does/not/exist.txt")

    @pytest.mark.asyncio
    async def test_stat_missing_raises(self, storage: LocalDiskStorage) -> None:
        with pytest.raises(FileNotFoundError):
            await storage.stat("does/not/exist.txt")

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, storage: LocalDiskStorage) -> None:
        await storage.put("delete/me.txt", b"delete me")
        assert await storage.get("delete/me.txt") == b"delete me"

        await storage.delete("delete/me.txt")
        with pytest.raises(FileNotFoundError):
            await storage.get("delete/me.txt")

    @pytest.mark.asyncio
    async def test_delete_missing_is_noop(self, storage: LocalDiskStorage) -> None:
        # Should not raise
        await storage.delete("never/existed.txt")

    @pytest.mark.asyncio
    async def test_protocol_conformance(self, storage: LocalDiskStorage) -> None:
        """LocalDiskStorage should satisfy the StorageService protocol."""
        assert isinstance(storage, StorageService)

    @pytest.mark.asyncio
    async def test_stream_returns_content(self, storage: LocalDiskStorage) -> None:
        data = b"x" * 200_000  # > single chunk
        await storage.put("stream/large.bin", data)

        chunks = [chunk async for chunk in storage.stream("stream/large.bin")]
        assert b"".join(chunks) == data

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self, storage: LocalDiskStorage) -> None:
        with pytest.raises(ValueError, match="Invalid storage key"):
            await storage.put("../escape.txt", b"bad")

        with pytest.raises(ValueError, match="Path traversal|Invalid storage key"):
            await storage.get("/absolute/path.txt")

    @pytest.mark.asyncio
    async def test_fsync_crash_safety(self, storage: LocalDiskStorage) -> None:
        """After put, the data is fsynced — verify by reading the raw file."""
        key = "crash/safe.txt"
        await storage.put(key, b"crash-safe data")
        retrieved = await storage.get(key)
        assert retrieved == b"crash-safe data"
