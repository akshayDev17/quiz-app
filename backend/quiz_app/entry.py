"""Cloudflare Workers (Python) entrypoint: the composition root over ``Api``.

``Default`` extends ``WorkerEntrypoint`` with ``async def fetch(self, request)``,
reading bindings from ``self.env`` and the Access identity from ``self.ctx``.
https://developers.cloudflare.com/workers/languages/python/
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

from .api import decode_body
from .auth import CloudflareAccessIdentity, parse_emails
from .composition import build_api


def _response(status: int, body: dict | None) -> Response:
    if status == 204 or body is None:
        return Response(None, status=status)  # a 204 carries neither body nor content-type
    return Response(json.dumps(body), headers={"content-type": "application/json"}, status=status)


def _path_of(request) -> str:
    """The request path. ``request.url`` is a JS string over the FFI boundary."""
    return urlsplit(str(request.url)).path


def _admin_emails(env) -> frozenset[str]:
    """``ADMIN_EMAILS`` is a Worker secret; a missing one means no admins."""
    raw = getattr(env, "ADMIN_EMAILS", "")
    return parse_emails(str(raw) if raw else "")


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        method = str(request.method).upper()
        body = None
        if method in ("POST", "PUT", "PATCH"):
            body = decode_body(str(await request.text()))
        identity = await CloudflareAccessIdentity(getattr(self, "ctx", None)).identify(request)
        api = build_api(self.env.DB, _admin_emails(self.env))
        status, payload = await api.handle(method, _path_of(request), body, identity)
        return _response(status, payload)
