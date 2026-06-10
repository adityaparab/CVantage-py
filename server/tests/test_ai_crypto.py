"""Tests for key encryption and AI model registry (issue #47)."""

from __future__ import annotations

import base64
import os

import pytest

from app.ai.crypto import CryptoService

# 32 random bytes, base64-encoded
_VALID_KEY = base64.b64encode(os.urandom(32)).decode("ascii")


class TestCryptoService:
    def test_round_trip(self) -> None:
        svc = CryptoService(_VALID_KEY)
        original = "sk-proj-abcdef123456"
        encrypted = svc.encrypt(original)
        assert encrypted != original
        decrypted = svc.decrypt(encrypted)
        assert decrypted == original

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValueError, match="is not configured"):
            CryptoService("")

    def test_wrong_key_length_raises(self) -> None:
        short_b64 = base64.b64encode(b"tooshort").decode("ascii")
        with pytest.raises(ValueError, match="must decode to 32 bytes"):
            CryptoService(short_b64)

    def test_tampered_ciphertext_raises(self) -> None:
        svc = CryptoService(_VALID_KEY)
        encrypted = svc.encrypt("secret-key")
        # Flip a byte in the ciphertext portion
        raw = bytearray(base64.b64decode(encrypted))
        raw[-1] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Decryption failed"):
            svc.decrypt(tampered)

    def test_different_keys_fail(self) -> None:
        svc1 = CryptoService(_VALID_KEY)
        key2 = base64.b64encode(os.urandom(32)).decode("ascii")
        svc2 = CryptoService(key2)
        encrypted = svc1.encrypt("secret")
        with pytest.raises(ValueError, match="Decryption failed"):
            svc2.decrypt(encrypted)

    def test_invalid_base64_raises(self) -> None:
        svc = CryptoService(_VALID_KEY)
        with pytest.raises(ValueError, match="Invalid encrypted payload"):
            svc.decrypt("not-base64!!")

    def test_too_short_payload_raises(self) -> None:
        svc = CryptoService(_VALID_KEY)
        short_b64 = base64.b64encode(b"short").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            svc.decrypt(short_b64)

    def test_deterministic_nonce_not_required(self) -> None:
        """Each encryption produces a different ciphertext (random nonce)."""
        svc = CryptoService(_VALID_KEY)
        e1 = svc.encrypt("same-value")
        e2 = svc.encrypt("same-value")
        assert e1 != e2
