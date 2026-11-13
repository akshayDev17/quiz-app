"""``HttpPost`` over the Workers runtime's ``fetch``, for the evaluator adapters.

Worker-only: ``js`` and ``pyodide`` exist only inside the Python Workers runtime, so this
module is imported lazily by ``entry.py`` and never by the services or the tests' graph.
``fetch`` is the JavaScript global, reached through the FFI ("Use JavaScript globals, like
fetch()", https://developers.cloudflare.com/workers/languages/python/ffi/), with the init
object converted by ``to_js(..., dict_converter=Object.fromEntries)`` as that page shows.

The key travels in ``headers`` only. Nothing here logs, and an exception from ``fetch``
(network failure, or the ``AbortSignal.timeout`` firing) propagates to the adapter, which
records it as "no answer" without reading its message.
"""

from __future__ import annotations

from js import AbortSignal, Object, fetch  # type: ignore[import-not-found]
from pyodide.ffi import to_js  # type: ignore[import-not-found]

from .evaluators import REQUEST_ID_HEADERS, HttpResponse


async def worker_post(url: str, headers: dict, body: str, timeout_s: float) -> HttpResponse:
    init = to_js(
        {
            "method": "POST",
            "headers": headers,
            "body": body,
            "signal": AbortSignal.timeout(int(timeout_s * 1000)),
        },
        dict_converter=Object.fromEntries,
    )
    response = await fetch(url, init)
    text = await response.text()
    # Headers.has, not a None check on get(): over the FFI a missing header's JS null
    # arrives as pyodide's `jsnull`, not None (seen in workerd), and would read "jsnull".
    kept = {name: str(response.headers.get(name)) for name in REQUEST_ID_HEADERS if response.headers.has(name)}
    return HttpResponse(int(response.status), kept, str(text))
