"""Between stored keys and working evaluators (ADR 0011).

``KeyRing`` seals what an admin enters for a key (``seal_key``, ``seal_billing``) and
opens a stored key into an evaluator (``evaluator``) or its billing values
(``balance_values``). Only this module and the adapters ever hold a plaintext key, and
only for the length of a request: nothing is cached across requests, logged or returned.

Without a cipher (``KEY_ENCRYPTION_KEY`` unset or malformed) nothing can be sealed or
opened, and every key reads as ``NO_KEY_STORAGE``.
"""

from __future__ import annotations

import json

from ..d1.evaluations import EvaluatorKey
from ..errors import Conflict, Invalid
from ..evaluators import Evaluator, Field, ProviderSpec
from ..keycipher import BILLING_PART, KEY_PART, CannotOpen, KeyCipher, additional_data
from ..transport import HttpSend

#: Why a stored key cannot be used, for admins.
NO_KEY_STORAGE = "key storage not set up (KEY_ENCRYPTION_KEY)"
KEY_UNREADABLE = "key cannot be decrypted with the current KEY_ENCRYPTION_KEY"
UNKNOWN_PROVIDER = "provider not available here"
BAD_KEY_VALUES = "key values no longer valid"


def read_fields(fields: tuple[Field, ...], payload: object, what: str, errors: list[str]) -> tuple[dict, dict]:
    """(secret values, plain values) of ``fields`` from an admin's payload, every field
    required and normalised; problems are appended to ``errors``, values never quoted."""
    body = payload if isinstance(payload, dict) else {}
    secrets: dict[str, str] = {}
    plain: dict[str, str] = {}
    for f in fields:
        raw = body.get(f.name)
        value = f.normalise(raw) if isinstance(raw, str) else None
        if value is None:
            errors.append(f"{what} {f.label.lower()} is missing or not valid")
            continue
        (secrets if f.secret else plain)[f.name] = value
    return secrets, plain


class KeyRing:
    def __init__(self, providers: dict[str, ProviderSpec], cipher: KeyCipher | None, send: HttpSend):
        self.providers = dict(providers)
        self._cipher = cipher
        self._send = send

    @property
    def ready(self) -> bool:
        return self._cipher is not None

    def spec(self, provider: str) -> ProviderSpec:
        spec = self.providers.get(provider)
        if spec is None:
            raise Invalid(f"provider must be one of {', '.join(sorted(self.providers))}")
        return spec

    def _require_cipher(self) -> KeyCipher:
        if self._cipher is None:
            raise Conflict("key storage is not set up: the owner must set the KEY_ENCRYPTION_KEY secret first")
        return self._cipher

    async def seal_key(self, provider: str, secrets: dict[str, str]) -> str:
        return await self._require_cipher().seal(json.dumps(secrets), additional_data(provider, KEY_PART))

    async def seal_billing(self, provider: str, secrets: dict[str, str]) -> str:
        return await self._require_cipher().seal(json.dumps(secrets), additional_data(provider, BILLING_PART))

    async def _open(self, sealed: str, provider: str, part: str) -> dict[str, str]:
        if self._cipher is None:
            raise CannotOpen()
        data = json.loads(await self._cipher.unseal(sealed, additional_data(provider, part)))
        if not isinstance(data, dict):
            raise CannotOpen()
        return {str(k): str(v) for k, v in data.items()}

    async def key_values(self, key: EvaluatorKey) -> dict[str, str]:
        """Every value of the key, secret and plain. Raises ``CannotOpen``."""
        return {**key.settings, **await self._open(key.sealed_key, key.provider, KEY_PART)}

    async def evaluator(self, key: EvaluatorKey) -> Evaluator | str:
        """The key's evaluator, or why there is none (one of the reasons above)."""
        spec = self.providers.get(key.provider)
        if spec is None:
            return UNKNOWN_PROVIDER
        if self._cipher is None:
            return NO_KEY_STORAGE
        try:
            values = await self.key_values(key)
        except (CannotOpen, ValueError):
            return KEY_UNREADABLE
        if any(f.name not in values for f in spec.key_fields):
            return BAD_KEY_VALUES
        evaluator = spec.build(values, self._send)
        return evaluator if evaluator is not None else BAD_KEY_VALUES

    def reads_balance(self, key: EvaluatorKey) -> bool:
        """Whether a "check now" can read a real budget figure for this key: its provider
        has a reader, and either the reader needs only the key or the key has a billing
        credential."""
        spec = self.providers.get(key.provider)
        return bool(spec and spec.read_balance and (not spec.billing_fields or key.sealed_billing))

    async def balance_values(self, key: EvaluatorKey) -> dict[str, str]:
        """The values a balance reader needs: the key's, plus its billing credential's when
        the provider has one. Raises ``CannotOpen``."""
        values = await self.key_values(key)
        if key.sealed_billing:
            values.update(key.billing_settings or {})
            values.update(await self._open(key.sealed_billing, key.provider, BILLING_PART))
        return values

    @property
    def send(self) -> HttpSend:
        return self._send
