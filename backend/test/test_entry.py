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


if __name__ == "__main__":
    unittest.main()
