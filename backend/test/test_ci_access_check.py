"""The deploy jobs' Cloudflare Access check, run against a fake Cloudflare API.

Each deploy job in .github/workflows/ci.yml embeds the check as a `python3 - <<'PY'`
heredoc. These tests execute every such script with `urllib.request.urlopen`
answered by fixtures, and assert whether it lets the deploy through.

Run:  python3 test/test_ci_access_check.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import textwrap
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
HOST = "akshayprabhakant.com"


def embedded_checks() -> list[str]:
    scripts, lines, inside = [], [], False
    for line in WORKFLOW.read_text().splitlines():
        if line.strip() == "python3 - <<'PY'":
            inside, lines = True, []
        elif inside and line.strip() == "PY":
            inside = False
            scripts.append(textwrap.dedent("\n".join(lines)))
        elif inside:
            lines.append(line)
    return scripts


def app(name, uris, policies):
    return {
        "name": name,
        "type": "self_hosted",
        "destinations": [{"type": "public", "uri": u} for u in uris],
        "policies": policies,
    }


ALLOW = {"id": "p-allow", "decision": "allow"}
DENY = {"id": "p-deny", "decision": "deny"}
BYPASS_EVERYONE = {"id": "p-bypass", "decision": "bypass"}
QUIZ_URIS = [f"{HOST}/quiz", f"{HOST}/quiz/*"]


def fake_cloudflare(apps, policies=None):
    def urlopen(req, timeout=None):
        path = urlparse(req.full_url).path
        if path.endswith("/access/apps"):
            body = {"success": True, "result": apps, "result_info": {"total_pages": 1}}
        else:
            policy_id = path.rsplit("/", 1)[-1]
            body = {"success": True, "result": (policies or {})[policy_id]}
        return io.BytesIO(json.dumps(body).encode())

    return urlopen


def run_check(script, apps, policies=None, path="/quiz"):
    env = {"CHECK_PATH": path, "CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "a"}
    out = io.StringIO()
    code = 0
    with mock.patch.dict(os.environ, env), \
            mock.patch("urllib.request.urlopen", fake_cloudflare(apps, policies)), \
            contextlib.redirect_stdout(out):
        try:
            exec(compile(script, "access-check", "exec"), {"__name__": "__main__"})
        except SystemExit as exit_:
            code = exit_.code or 0
    return code, out.getvalue()


class AccessCheckCase(unittest.TestCase):
    def setUp(self):
        self.scripts = embedded_checks()

    def assertVerdict(self, expected_code, apps, policies=None, path="/quiz"):
        for i, script in enumerate(self.scripts):
            with self.subTest(job=i):
                code, out = run_check(script, apps, policies, path)
                self.assertEqual(code, expected_code, out)

    def test_both_deploy_jobs_carry_the_check(self):
        self.assertEqual(len(self.scripts), 2)

    def test_quiz_app_with_allow_passes(self):
        self.assertVerdict(0, [app("Quiz Room", QUIZ_URIS, [ALLOW])])

    def test_reusable_policy_is_looked_up_by_id(self):
        self.assertVerdict(0, [app("Quiz Room", QUIZ_URIS, ["p-allow"])], {"p-allow": ALLOW})

    def test_no_covering_app_refuses(self):
        self.assertVerdict(1, [app("Archive", [f"{HOST}/chat-archives"], [ALLOW])])

    def test_wildcard_does_not_cover_its_parent_path(self):
        self.assertVerdict(1, [app("Quiz Room", [f"{HOST}/quiz/*"], [ALLOW])])

    def test_bypass_everyone_plus_allow_refuses(self):
        self.assertVerdict(1, [app("Quiz Room", QUIZ_URIS, [BYPASS_EVERYONE, ALLOW])])

    def test_reusable_bypass_policy_refuses(self):
        self.assertVerdict(
            1, [app("Quiz Room", QUIZ_URIS, ["p-bypass", "p-allow"])],
            {"p-bypass": BYPASS_EVERYONE, "p-allow": ALLOW},
        )

    def test_specific_app_without_allow_overrides_broad_allow(self):
        broad = app("Whole site", [f"{HOST}/*"], [ALLOW])
        for policies in ([BYPASS_EVERYONE], [DENY], []):
            with self.subTest(specific=policies):
                self.assertVerdict(1, [broad, app("Quiz Room", [f"{HOST}/quiz"], policies)])

    def test_specific_app_with_allow_overrides_broad_bypass(self):
        broad = app("Whole site", [f"{HOST}/*"], [BYPASS_EVERYONE])
        self.assertVerdict(0, [broad, app("Quiz Room", QUIZ_URIS, [ALLOW])])

    def test_longer_wildcard_prefix_overrides_shorter(self):
        broad = app("Whole site", [f"{HOST}/*"], [ALLOW])
        quiz = app("Quiz Room", [f"{HOST}/quiz/*"], [DENY])
        self.assertVerdict(1, [broad, quiz], path="/quiz/admin")


if __name__ == "__main__":
    unittest.main()
