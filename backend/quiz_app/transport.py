"""The one outbound-HTTP shape every provider adapter and billing reader uses.

``send(method, url, headers, body, timeout_s)`` returns an ``HttpResponse`` and raises on a
network failure or timeout. The Worker's ``send`` is ``worker_http.worker_send`` (the
runtime's ``fetch``); ``urllib_send`` serves ``local_server.py`` and dev tools; tests pass
their own. Keys and tokens travel only in ``headers`` (or a form ``body`` for an OAuth token
request), never in a URL, and nothing here logs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

#: Response headers kept, for the request id logged with each call. Nothing else is kept.
REQUEST_ID_HEADERS = ("request-id", "x-amzn-requestid", "apim-request-id")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]   # lowercased names; only those in REQUEST_ID_HEADERS are kept
    text: str


HttpSend = Callable[[str, str, dict, "str | None", float], Awaitable[HttpResponse]]
"""``send(method, url, headers, body, timeout_s)``. Raises on a network failure or timeout."""


async def urllib_send(method: str, url: str, headers: dict, body: str | None, timeout_s: float) -> HttpResponse:
    """``HttpSend`` over ``urllib``, run in a thread. For ``local_server.py`` and dev tools."""
    import urllib.error
    import urllib.request

    def call() -> HttpResponse:
        data = body.encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 (https only)
                status, raw, got = response.status, response.read(), response.headers
        except urllib.error.HTTPError as e:
            status, raw, got = e.code, e.read(), e.headers
        kept = {h: got.get(h) for h in REQUEST_ID_HEADERS if got.get(h)}
        return HttpResponse(status, kept, raw.decode("utf-8", "replace"))

    return await asyncio.get_running_loop().run_in_executor(None, call)
