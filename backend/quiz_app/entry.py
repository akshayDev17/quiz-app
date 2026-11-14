"""Cloudflare Workers (Python) entrypoint: the composition root over ``Api``.

``Default`` extends ``WorkerEntrypoint`` with ``async def fetch(self, request)``,
reading bindings from ``self.env`` and the Access identity from ``self.ctx``.
https://developers.cloudflare.com/workers/languages/python/
"""

from __future__ import annotations

import json

from workers import Response, WorkerEntrypoint

from .api import decode_body, response_headers
from .auth import CloudflareAccessIdentity, parse_emails, request_path
from .composition import build_api, settings_from
from .keycipher import MASTER_KEY_SECRET, master_key


def _response(status: int, body: dict | None, extra: dict[str, str] | None = None) -> Response:
    """``extra`` holds headers beyond content-type, from ``api.response_headers``."""
    extra = extra or {}
    if status == 204 or body is None:
        # An empty string, not None: empty-string bodies are proven on Python Workers.
        # A 204 carries neither body nor content-type.
        return Response("", headers=extra or None, status=status)
    return Response(json.dumps(body), headers={"content-type": "application/json", **extra}, status=status)


def _admin_emails(env) -> frozenset[str]:
    """``ADMIN_EMAILS`` is a Worker secret; a missing one means no admins."""
    raw = getattr(env, "ADMIN_EMAILS", "")
    return parse_emails(str(raw) if raw else "")


def _setting(env, name: str) -> str | None:
    """A Worker secret or var as text, or ``None`` when it is not set. Never logged."""
    value = getattr(env, name, None)
    return str(value) if value is not None else None


def _cipher(env):
    """The key cipher under the ``KEY_ENCRYPTION_KEY`` secret, or ``None`` when that secret
    is missing or is not 32 bytes of base64: then no evaluator key can be stored or used."""
    key = master_key(_setting(env, MASTER_KEY_SECRET))
    if key is None:
        return None
    from .worker_crypto import WebCryptoCipher  # Worker-only: needs the js and pyodide modules

    return WebCryptoCipher(key)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        method = str(request.method).upper()
        body = None
        if method in ("POST", "PUT", "PATCH"):
            body = decode_body(str(await request.text()))
        identity = await CloudflareAccessIdentity(getattr(self, "ctx", None)).identify(request)
        from .worker_http import worker_send  # Worker-only: needs the js and pyodide modules

        api = build_api(
            self.env.DB,
            _admin_emails(self.env),
            cipher=_cipher(self.env),
            send=worker_send,
            settings=settings_from(lambda name: _setting(self.env, name)),
        )
        path = request_path(request)
        status, payload = await api.handle(method, path, body, identity)
        return _response(status, payload, response_headers(path, status))
