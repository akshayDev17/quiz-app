"""The Worker entrypoint's response mapping, with the ``workers`` runtime module stubbed.

``workers`` exists only on Cloudflare, so a recording stub stands in for it.

Run:  python3 test/test_entry.py
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class _Response:
    def __init__(self, body=None, headers=None, status=200):
        self.body, self.headers, self.status = body, headers, status


class _WorkerEntrypoint:
    pass


_MISSING = object()
_saved = _MISSING
entry = None


def setUpModule():
    global _saved, entry
    _saved = sys.modules.get("workers", _MISSING)
    stub = types.ModuleType("workers")
    stub.Response, stub.WorkerEntrypoint = _Response, _WorkerEntrypoint
    sys.modules["workers"] = stub
    sys.modules.pop("quiz_app.entry", None)
    from quiz_app import entry as module

    entry = module


def tearDownModule():
    sys.modules.pop("quiz_app.entry", None)
    if _saved is _MISSING:
        sys.modules.pop("workers", None)
    else:
        sys.modules["workers"] = _saved


class ResponseMappingTest(unittest.TestCase):
    def test_204_has_an_empty_string_body_and_no_content_type(self):
        r = entry._response(204, None)
        self.assertEqual((r.status, r.body, r.headers), (204, "", None))

    def test_204_ignores_a_payload(self):
        r = entry._response(204, {"ignored": True})
        self.assertEqual((r.status, r.body, r.headers), (204, "", None))

    def test_json_payload_is_serialised_with_a_content_type(self):
        r = entry._response(200, {"a": 1})
        self.assertEqual((r.status, r.body), (200, '{"a": 1}'))
        self.assertEqual(r.headers, {"content-type": "application/json"})

    def test_missing_payload_on_other_statuses_is_also_empty(self):
        r = entry._response(404, None)
        self.assertEqual((r.status, r.body, r.headers), (404, "", None))

    def test_extra_headers_join_the_content_type(self):
        r = entry._response(200, {"a": 1}, {"cache-control": "public, max-age=60"})
        self.assertEqual(
            r.headers, {"content-type": "application/json", "cache-control": "public, max-age=60"}
        )

    def test_extra_headers_survive_an_empty_body(self):
        r = entry._response(404, None, {"allow": "GET"})
        self.assertEqual((r.status, r.body, r.headers), (404, "", {"allow": "GET"}))


class WorkerPostTest(unittest.IsolatedAsyncioTestCase):
    """The Worker's ``fetch`` shim, with ``js`` and ``pyodide.ffi`` stubbed: what it hands to
    ``fetch``, and how it reads the status, the request id and the body back."""

    async def asyncSetUp(self):
        self.saved = {name: sys.modules.get(name, _MISSING) for name in ("js", "pyodide", "pyodide.ffi")}
        self.sent = []

        class JsNull:  # what a JS null looks like over pyodide's FFI: not None
            def __str__(self):
                return "jsnull"

        class Headers:
            present = {"request-id": "req_42"}

            def has(self, name):
                return name in self.present

            def get(self, name):
                return self.present.get(name, JsNull())

        class FetchResponse:
            status = 200
            headers = Headers()

            async def text(self):
                return '{"ok": true}'

        async def fetch(url, init):
            self.sent.append((url, init))
            return FetchResponse()

        js = types.ModuleType("js")
        js.fetch = fetch
        js.Object = types.SimpleNamespace(fromEntries="fromEntries")
        js.AbortSignal = types.SimpleNamespace(timeout=lambda ms: ("signal", ms))
        ffi = types.ModuleType("pyodide.ffi")
        ffi.to_js = lambda value, dict_converter=None: {"converted_by": dict_converter, **value}
        sys.modules.update({"js": js, "pyodide": types.ModuleType("pyodide"), "pyodide.ffi": ffi})
        sys.modules.pop("quiz_app.worker_http", None)
        from quiz_app import worker_http

        self.worker_http = worker_http

    async def asyncTearDown(self):
        sys.modules.pop("quiz_app.worker_http", None)
        for name, module in self.saved.items():
            if module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    async def test_posts_headers_and_body_with_a_timeout_and_reads_the_reply(self):
        got = await self.worker_http.worker_post(
            "https://api.example/v1/messages", {"x-api-key": "k"}, '{"a": 1}', 25.0
        )
        [(url, init)] = self.sent
        self.assertEqual(url, "https://api.example/v1/messages")
        self.assertEqual(init, {
            "converted_by": "fromEntries", "method": "POST", "headers": {"x-api-key": "k"},
            "body": '{"a": 1}', "signal": ("signal", 25_000),
        })
        self.assertEqual((got.status, got.headers, got.text), (200, {"request-id": "req_42"}, '{"ok": true}'))


if __name__ == "__main__":
    unittest.main()
