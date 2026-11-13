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
from .composition import build_api, quotas_from
from .evaluators import usable_evaluators


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


def _evaluators(env) -> dict:
    """The evaluator of every provider whose secrets are set (``evaluators.PROVIDERS``:
    ``ANTHROPIC_API_KEY``; ``BEDROCK_API_KEY`` + ``BEDROCK_REGION``;
    ``AZURE_FOUNDRY_API_KEY`` + ``AZURE_FOUNDRY_ENDPOINT``). Never the fake."""
    from .worker_http import worker_post  # Worker-only: needs the js and pyodide modules

    return usable_evaluators(lambda name: _setting(env, name), worker_post)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        method = str(request.method).upper()
        body = None
        if method in ("POST", "PUT", "PATCH"):
            body = decode_body(str(await request.text()))
        identity = await CloudflareAccessIdentity(getattr(self, "ctx", None)).identify(request)
        api = build_api(
            self.env.DB,
            _admin_emails(self.env),
            evaluators=_evaluators(self.env),
            quotas=quotas_from(lambda name: _setting(self.env, name)),
        )
        path = request_path(request)
        status, payload = await api.handle(method, path, body, identity)
        return _response(status, payload, response_headers(path, status))
