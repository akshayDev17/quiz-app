"""``KeyCipher`` over the Workers runtime's Web Crypto (``crypto.subtle``), AES-256-GCM.

Worker-only, like ``worker_http``: ``js`` and ``pyodide`` exist only inside the Python
Workers runtime, so ``entry.py`` imports this lazily. The sealed format is
``keycipher.pack``'s, the same as ``CryptographyCipher``'s, so a value sealed by one opens
with the other (checked in workerd against the ``cryptography`` package).
"""

from __future__ import annotations

from js import Object, Uint8Array, crypto  # type: ignore[import-not-found]
from pyodide.ffi import to_js  # type: ignore[import-not-found]

from .keycipher import IV_BYTES, CannotOpen, KeyCipher, pack, unpack


def _bytes_of(buffer) -> bytes:
    """A JS ArrayBuffer (or typed array) as Python bytes."""
    return bytes(Uint8Array.new(buffer).to_py())


class WebCryptoCipher(KeyCipher):
    def __init__(self, key: bytes):
        self._raw = key
        self._key = None

    async def _crypto_key(self):
        if self._key is None:
            self._key = await crypto.subtle.importKey(
                "raw", to_js(self._raw), "AES-GCM", False, to_js(["encrypt", "decrypt"]),
            )
        return self._key

    def _params(self, iv: bytes, aad: bytes):
        return to_js(
            {"name": "AES-GCM", "iv": to_js(iv), "additionalData": to_js(aad), "tagLength": 128},
            dict_converter=Object.fromEntries,
        )

    async def seal(self, plaintext: str, aad: bytes) -> str:
        iv = _bytes_of(crypto.getRandomValues(Uint8Array.new(IV_BYTES)))
        sealed = await crypto.subtle.encrypt(
            self._params(iv, aad), await self._crypto_key(), to_js(plaintext.encode("utf-8")),
        )
        return pack(iv, _bytes_of(sealed))

    async def unseal(self, value: str, aad: bytes) -> str:
        iv, sealed = unpack(value)
        try:
            plain = await crypto.subtle.decrypt(self._params(iv, aad), await self._crypto_key(), to_js(sealed))
            return _bytes_of(plain).decode("utf-8")
        except Exception:
            raise CannotOpen() from None
