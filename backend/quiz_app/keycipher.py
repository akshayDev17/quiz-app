"""Evaluator keys at rest: AES-256-GCM under the ``KEY_ENCRYPTION_KEY`` secret (ADR 0011).

The admin pastes provider keys into the admin page; D1 stores them only sealed. A sealed
value is ``v1:`` + base64(12-byte random IV, then the ciphertext with its 16-byte tag),
and it is sealed with additional data naming what it holds
(``evaluator-credential:<provider>:<part>``), so a value copied into another provider's
row, or from the key part into the billing part, fails to open instead of being misused.

The master key is 32 random bytes, base64-encoded, set once by the owner with
``wrangler secret put KEY_ENCRYPTION_KEY``. It never enters D1, a log or a response.
Without it there is no cipher: keys can be neither added nor used, and the admin page
says why.

``KeyCipher`` is the port. The Worker's implementation is ``worker_crypto.WebCryptoCipher``
(Web Crypto, imported lazily: it needs the Workers runtime); ``CryptographyCipher`` serves
``local_server.py`` when the ``cryptography`` package is installed; tests use a stand-in.
"""

from __future__ import annotations

import base64
import binascii
from abc import ABC, abstractmethod

PREFIX = "v1:"
IV_BYTES = 12
TAG_BYTES = 16
MASTER_KEY_BYTES = 32
MASTER_KEY_SECRET = "KEY_ENCRYPTION_KEY"

#: The parts of a credential that are sealed separately.
KEY_PART, BILLING_PART = "key", "billing"


class CannotOpen(Exception):
    """A sealed value that does not open: wrong master key, tampered, or not ours. Carries no
    detail on purpose."""


def master_key(raw: str | None) -> bytes | None:
    """The master key from its base64 text, or ``None`` when it is missing or is not exactly
    32 bytes."""
    if raw is None or not str(raw).strip():
        return None
    try:
        key = base64.b64decode(str(raw).strip(), validate=True)
    except (binascii.Error, ValueError):
        return None
    return key if len(key) == MASTER_KEY_BYTES else None


def additional_data(provider: str, part: str) -> bytes:
    return f"evaluator-credential:{provider}:{part}".encode()


def pack(iv: bytes, sealed: bytes) -> str:
    return PREFIX + base64.b64encode(iv + sealed).decode("ascii")


def unpack(value: str) -> tuple[bytes, bytes]:
    """(IV, ciphertext with tag) of a sealed value. Raises ``CannotOpen``."""
    if not isinstance(value, str) or not value.startswith(PREFIX):
        raise CannotOpen()
    try:
        raw = base64.b64decode(value[len(PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        raise CannotOpen() from None
    if len(raw) < IV_BYTES + TAG_BYTES:
        raise CannotOpen()
    return raw[:IV_BYTES], raw[IV_BYTES:]


class KeyCipher(ABC):
    @abstractmethod
    async def seal(self, plaintext: str, aad: bytes) -> str:
        """``plaintext`` sealed under the master key with a fresh random IV."""

    @abstractmethod
    async def unseal(self, value: str, aad: bytes) -> str:
        """The plaintext of a sealed value. Raises ``CannotOpen`` on any failure."""


class CryptographyCipher(KeyCipher):
    """AES-256-GCM through the ``cryptography`` package: for ``local_server.py`` only. The
    Worker has no such dependency and uses Web Crypto instead; the sealed format is the same."""

    def __init__(self, key: bytes):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self._aead = AESGCM(key)

    async def seal(self, plaintext: str, aad: bytes) -> str:
        import os

        iv = os.urandom(IV_BYTES)
        return pack(iv, self._aead.encrypt(iv, plaintext.encode("utf-8"), aad))

    async def unseal(self, value: str, aad: bytes) -> str:
        iv, sealed = unpack(value)
        try:
            return self._aead.decrypt(iv, sealed, aad).decode("utf-8")
        except Exception:
            raise CannotOpen() from None
