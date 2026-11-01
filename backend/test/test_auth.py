"""``CloudflareAccessIdentity``: one retry of ``getIdentity()``, and one log line per miss naming its branch.

Run:  python3 test/test_auth.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.auth import CloudflareAccessIdentity, Identity, request_path  # noqa: E402

EMAIL = "Alice@Example.com"
# Values a request carries that must never reach a log line.
COOKIE = "CF_Authorization=eyJhbGciOiJSUzI1NiJ9.secret-cookie-token"
JWT = "eyJhbGciOiJSUzI1NiJ9.secret-assertion-token"


def _request(path="/quiz/api/topics"):
    return SimpleNamespace(
        url=f"https://akshayprabhakant.com{path}?q=1",
        headers={"cookie": COOKIE, "cf-access-jwt-assertion": JWT, "cf-access-authenticated-user-email": EMAIL},
    )


class _Access:
    """``ctx.access`` whose ``getIdentity()`` plays back one scripted outcome per call."""

    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    async def getIdentity(self):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _signed_in(email=EMAIL):
    return SimpleNamespace(email=email)


class IdentityCase(unittest.IsolatedAsyncioTestCase):
    async def identify(self, ctx, request=None):
        """Identify with no retry pause, returning ``(identity, parsed log lines)``."""
        lines: list[str] = []
        provider = CloudflareAccessIdentity(ctx, retry_delay_s=0, log=lines.append)
        identity = await provider.identify(_request() if request is None else request)
        for line in lines:
            for secret in (COOKIE, JWT, EMAIL, EMAIL.lower(), "secret"):
                self.assertNotIn(secret, line)
        return identity, [json.loads(line) for line in lines]


class FirstTryTest(IdentityCase):
    async def test_a_resolved_email_is_the_identity_with_no_retry_and_no_log(self):
        access = _Access(_signed_in())
        identity, logs = await self.identify(SimpleNamespace(access=access))
        self.assertEqual(identity, Identity(EMAIL))
        self.assertEqual((access.calls, logs), (1, []))


class RetryTest(IdentityCase):
    async def test_a_throw_then_an_email_recovers_and_logs_the_recovery(self):
        access = _Access(RuntimeError("Network connection lost."), _signed_in())
        identity, logs = await self.identify(SimpleNamespace(access=access))
        self.assertEqual(identity, Identity(EMAIL))
        self.assertEqual(access.calls, 2)
        self.assertEqual(logs, [{
            "event": "access_identity_recovered",
            "path": "/quiz/api/topics",
            "branch": "identity-threw",
            "attempts": [
                {"branch": "identity-threw", "error_class": "RuntimeError", "error": "Network connection lost."},
            ],
        }])

    async def test_no_email_then_an_email_recovers(self):
        access = _Access(SimpleNamespace(email=None), _signed_in())
        identity, logs = await self.identify(SimpleNamespace(access=access))
        self.assertEqual(identity, Identity(EMAIL))
        self.assertEqual([log["event"] for log in logs], ["access_identity_recovered"])
        self.assertEqual(logs[0]["attempts"], [{"branch": "no-email"}])

    async def test_retries_once_only(self):
        access = _Access(RuntimeError("one"), RuntimeError("two"), _signed_in())
        identity, _ = await self.identify(SimpleNamespace(access=access))
        self.assertIsNone(identity)
        self.assertEqual(access.calls, 2)


class MissLogTest(IdentityCase):
    async def test_access_missing_is_not_retried_and_logs_its_branch(self):
        identity, logs = await self.identify(SimpleNamespace(), _request("/quiz/api/me"))
        self.assertIsNone(identity)
        self.assertEqual(logs, [{
            "event": "access_identity_missing",
            "path": "/quiz/api/me",
            "branch": "access-missing",
            "attempts": [{"branch": "access-missing"}],
        }])

    async def test_no_ctx_at_all_is_access_missing(self):
        identity, logs = await self.identify(None)
        self.assertIsNone(identity)
        self.assertEqual(logs[0]["branch"], "access-missing")

    async def test_an_unreadable_access_binding_is_access_missing_with_its_error(self):
        class _Ctx:
            @property
            def access(self):
                raise RuntimeError("proxy gone")

        identity, logs = await self.identify(_Ctx())
        self.assertIsNone(identity)
        self.assertEqual(
            logs[0]["attempts"],
            [{"branch": "access-missing", "error_class": "RuntimeError", "error": "proxy gone"}],
        )

    async def test_get_identity_throwing_twice_logs_both_errors(self):
        access = _Access(TypeError("first"), RuntimeError("second"))
        identity, logs = await self.identify(SimpleNamespace(access=access))
        self.assertIsNone(identity)
        self.assertEqual(logs, [{
            "event": "access_identity_missing",
            "path": "/quiz/api/topics",
            "branch": "identity-threw",
            "attempts": [
                {"branch": "identity-threw", "error_class": "TypeError", "error": "first"},
                {"branch": "identity-threw", "error_class": "RuntimeError", "error": "second"},
            ],
        }])

    async def test_resolving_without_an_email_twice_logs_no_email(self):
        access = _Access(None, SimpleNamespace(email=""))
        identity, logs = await self.identify(SimpleNamespace(access=access))
        self.assertIsNone(identity)
        self.assertEqual(logs[0]["branch"], "no-email")
        self.assertEqual(logs[0]["attempts"], [{"branch": "no-email"}, {"branch": "no-email"}])

    async def test_an_unreadable_email_counts_as_a_throw(self):
        class _Identity:
            @property
            def email(self):
                raise RuntimeError("proxy gone")

        identity, logs = await self.identify(SimpleNamespace(access=_Access(_Identity(), _Identity())))
        self.assertIsNone(identity)
        self.assertEqual(logs[0]["branch"], "identity-threw")

    async def test_a_long_error_message_is_truncated(self):
        access = _Access(RuntimeError("x" * 1000), RuntimeError("y" * 1000))
        _, logs = await self.identify(SimpleNamespace(access=access))
        self.assertEqual(len(logs[0]["attempts"][1]["error"]), 200)

    async def test_the_query_string_never_reaches_the_log(self):
        _, logs = await self.identify(SimpleNamespace())
        self.assertEqual(logs[0]["path"], "/quiz/api/topics")


class RequestPathTest(unittest.TestCase):
    def test_path_without_query(self):
        self.assertEqual(request_path(_request("/quiz/api/attempts/a1")), "/quiz/api/attempts/a1")

    def test_no_request_is_an_empty_path(self):
        self.assertEqual(request_path(None), "")


if __name__ == "__main__":
    unittest.main()
