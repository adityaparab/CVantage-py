"""AES-256-GCM encryption service for provider API keys (issue #47)."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoService:
    """Encrypts/decrypts provider API keys using AES-256-GCM.

    Key must be a 32-byte value, provided as a base64-encoded string
    via the ``MASTER_ENCRYPTION_KEY`` env variable.
    """

    def __init__(self, key_b64: str) -> None:
        if not key_b64:
            raise ValueError("MASTER_ENCRYPTION_KEY is not configured")
        try:
            self._key = base64.b64decode(key_b64)
        except Exception as e:
            raise ValueError(f"Invalid MASTER_ENCRYPTION_KEY: {e}") from e
        if len(self._key) != 32:
            raise ValueError(f"MASTER_ENCRYPTION_KEY must decode to 32 bytes, got {len(self._key)}")
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return a base64 string: nonce || ciphertext || tag."""
        data = plaintext.encode("utf-8")
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self._aesgcm.encrypt(nonce, data, None)
        # nonce + ciphertext (includes tag)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a value produced by ``encrypt``. Raises on tamper."""
        try:
            raw = base64.b64decode(encrypted)
        except Exception as e:
            raise ValueError(f"Invalid encrypted payload: {e}") from e

        if len(raw) < 12 + 16:  # nonce (12) + minimum ciphertext+tag (16)
            raise ValueError("Encrypted payload is too short")

        nonce = raw[:12]
        ciphertext = raw[12:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            raise ValueError(f"Decryption failed (tampered or wrong key): {e}") from e

        return plaintext.decode("utf-8")
