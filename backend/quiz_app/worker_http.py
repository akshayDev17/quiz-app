"""``HttpSend`` over the Workers runtime's ``fetch``, for the evaluator adapters and the
billing readers.

Worker-only: ``js`` and ``pyodide`` exist only inside the Python Workers runtime, so this
module is imported lazily by ``entry.py`` and never by the services or the tests' graph.
``fetch`` is the JavaScript global, reached through the FFI ("Use JavaScript globals, like
fetch()", https://developers.cloudflare.com/workers/languages/python/ffi/), with the init
object converted by ``to_js(..., dict_converter=Object.fromEntries)`` as that page shows.

Keys travel in ``headers`` only (an OAuth client secret in a form ``body``). Nothing here
logs, and an exception from ``fetch`` (network failure, or the ``AbortSignal.timeout``
firing) propagates to the caller, which records it without reading its message.
"""

from __future__ import annotations

from js import AbortSignal, Object, fetch  # type: ignore[import-not-found]
from pyodide.ffi import to_js  # type: ignore[import-not-found]

from .transport import REQUEST_ID_HEADERS, HttpResponse


async def worker_send(method: str, url: str, headers: dict, body: str | None, timeout_s: float) -> HttpResponse:
    init = {"method": method, "headers": headers, "signal": AbortSignal.timeout(int(timeout_s * 1000))}
    if body is not None:
        init["body"] = body
    response = await fetch(url, to_js(init, dict_converter=Object.fromEntries))
    text = await response.text()
    # Headers.has, not a None check on get(): over the FFI a missing header's JS null
    # arrives as pyodide's `jsnull`, not None (seen in workerd), and would read "jsnull".
    kept = {name: str(response.headers.get(name)) for name in REQUEST_ID_HEADERS if response.headers.has(name)}
    return HttpResponse(int(response.status), kept, str(text))
