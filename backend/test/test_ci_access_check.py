"""The deploy jobs' Cloudflare Access check, run against a fake Cloudflare API.

Both deploy jobs in .github/workflows/ci.yml run .github/scripts/access_check.py
before they deploy. These tests run its `main()` with `urllib.request.urlopen`
answered by fixtures, and assert whether it lets the deploy through. The rules
themselves are tested on flat records in .github/scripts/test_access_check.py;
this file covers what `main()` does with the API: auth, pagination, policy
lookup, destination fields, errors and the exit code.

Run:  uv run python test/test_ci_access_check.py
"""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
SCRIPTS = ROOT / ".github" / "scripts"
CHECK_RUN = "python3 .github/scripts/access_check.py"

sys.path.insert(0, str(SCRIPTS))
import access_check  # noqa: E402
from test_access_check import PLANNED, STEP_ONE, TODAY  # noqa: E402

HOST = access_check.HOST
QUIZ_URIS = [f"{HOST}/quiz", f"{HOST}/quiz/*"]


def api_app(name, uris, policies, type="self_hosted"):
    return {
        "name": name,
        "type": type,
        "destinations": [{"type": "public", "uri": u} for u in uris],
        "policies": policies,
    }


def api_form(flat_apps):
    return [
        api_app(a["name"], a["uris"], [{"id": f"p-{d}", "decision": d} for d in a["decisions"]], a["type"])
        for a in flat_apps
    ]


def fake_cloudflare(pages, policies=None, seen=None, total_pages=True, error=None):
    def urlopen(req, timeout=None):
        # http.client refuses these before sending; the real deploy failed this way.
        for value in req.headers.values():
            if http.client._is_illegal_header_value(value.encode()):
                raise ValueError(f"Invalid header value {value.encode()!r}")
        if seen is not None:
            seen.append(req)
        if error is not None:
            status, body = error
            raise urllib.error.HTTPError(req.full_url, status, "error", {}, io.BytesIO(json.dumps(body).encode()))
        url = urlparse(req.full_url)
        if url.path.endswith("/access/apps"):
            page = int(parse_qs(url.query)["page"][0])
            body = {"success": True, "result": pages[page - 1] if page <= len(pages) else []}
            if total_pages:
                body["result_info"] = {"page": page, "total_pages": len(pages)}
        else:
            body = {"success": True, "result": (policies or {})[url.path.rsplit("/", 1)[-1]]}
        return io.BytesIO(json.dumps(body).encode())

    return urlopen


def run_check(apps=None, *, pages=None, policies=None, token="t", account="a", seen=None,
              total_pages=True, error=None):
    env = {"CLOUDFLARE_API_TOKEN": token, "CLOUDFLARE_ACCOUNT_ID": account}
    urlopen = fake_cloudflare(pages if pages is not None else [apps], policies, seen, total_pages, error)
    out = io.StringIO()
    code = 0
    with mock.patch.dict(os.environ, env), \
            mock.patch("urllib.request.urlopen", urlopen), \
            contextlib.redirect_stdout(out):
        try:
            access_check.main()
        except SystemExit as exit_:
            code = exit_.code or 0
    return code, out.getvalue()


def app_requests(seen):
    return [r for r in seen if urlparse(r.full_url).path.endswith("/access/apps")]


def policy_requests(seen):
    return [urlparse(r.full_url).path.rsplit("/", 1)[-1] for r in seen if "/access/policies/" in r.full_url]


class DeployJobs(unittest.TestCase):
    def test_every_production_job_checks_access_before_running_wrangler(self):
        jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
        production = {name: job for name, job in jobs.items() if job.get("environment") == "production"}
        self.assertEqual(set(production), {"deploy-api", "deploy-frontend"})
        for name, job in production.items():
            with self.subTest(job=name):
                runs = [step.get("run", "") for step in job["steps"]]
                self.assertIn(CHECK_RUN, runs)
                check = runs.index(CHECK_RUN)
                deploys = [i for i, run in enumerate(runs) if "wrangler" in run]
                self.assertTrue(deploys, f"{name} runs no wrangler step")
                self.assertLess(check, min(deploys))
                env = job["steps"][check].get("env", {})
                self.assertEqual(env.get("CLOUDFLARE_API_TOKEN"), "${{ secrets.CLOUDFLARE_API_TOKEN }}")
                self.assertEqual(env.get("CLOUDFLARE_ACCOUNT_ID"), "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}")


class Verdict(unittest.TestCase):
    def test_live_and_planned_configs_deploy(self):
        for label, flat in [("today", TODAY), ("step one", STEP_ONE), ("planned", PLANNED)]:
            with self.subTest(config=label):
                code, out = run_check(api_form(flat))
                self.assertEqual(code, 0, out)
                self.assertNotIn("::error::", out)
                self.assertIn(f"{HOST}/quiz/set: signed in only", out)

    def test_planned_config_reports_the_public_paths(self):
        code, out = run_check(api_form(PLANNED))
        self.assertEqual(code, 0, out)
        self.assertIn(f"{HOST}/quiz/view: public, by the Bypass on 'Quiz Room (public)'.", out)

    def test_refusal_exits_1_with_an_error_annotation(self):
        code, out = run_check([api_app("Archive", [f"{HOST}/chat-archives"], [{"decision": "allow"}])])
        self.assertEqual(code, 1, out)
        self.assertIn(f"::error::No Cloudflare Access self-hosted application covers {HOST}/quiz/set.", out)

    def test_broad_bypass_refuses_even_under_a_specific_allow_app(self):
        for uri in [HOST, f"{HOST}/*"]:
            with self.subTest(broad=uri):
                broad = api_app("Whole site", [uri], [{"decision": "bypass"}])
                code, out = run_check([broad, api_app("Quiz Room", QUIZ_URIS, [{"decision": "allow"}])])
                self.assertEqual(code, 1, out)
                self.assertIn("'Whole site' has a Bypass policy", out)


class Requests(unittest.TestCase):
    def test_token_and_account_with_trailing_newline_are_stripped(self):
        seen = []
        code, out = run_check(api_form(TODAY), token="t\n", account="a\n", seen=seen)
        self.assertEqual(code, 0, out)
        self.assertTrue(seen, out)
        for req in seen:
            self.assertEqual(req.get_header("Authorization"), "Bearer t")
            self.assertTrue(req.full_url.startswith("https://api.cloudflare.com/client/v4/accounts/a/"), req.full_url)

    def test_missing_secrets_refuse_without_calling_the_api(self):
        for token, account in [("", "a"), ("t", ""), ("\n", "a")]:
            with self.subTest(token=token, account=account):
                seen = []
                code, out = run_check(api_form(TODAY), token=token, account=account, seen=seen)
                self.assertEqual(code, 1, out)
                self.assertIn("CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must both be set", out)
                self.assertEqual(seen, [])

    def test_unreadable_access_names_the_missing_permission(self):
        for status in (401, 403):
            with self.subTest(status=status):
                code, out = run_check([], error=(status, {"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]}))
                self.assertEqual(code, 1, out)
                self.assertIn(f"cannot read Cloudflare Access (HTTP {status})", out)
                self.assertIn(access_check.PERMISSION, out)

    def test_other_api_errors_refuse_with_cloudflares_message(self):
        code, out = run_check([], error=(500, {"success": False, "errors": [{"code": 1, "message": "upstream down"}]}))
        self.assertEqual(code, 1, out)
        self.assertIn("returned HTTP 500", out)
        self.assertIn("upstream down", out)

    def test_apps_are_read_from_every_page(self):
        filler = [api_app(f"other {i}", [f"other{i}.example.org/*"], []) for i in range(100)]
        quiz = api_form(TODAY)
        for total_pages in (True, False):
            with self.subTest(total_pages=total_pages):
                seen = []
                code, out = run_check(pages=[filler, quiz], seen=seen, total_pages=total_pages)
                self.assertEqual(code, 0, out)
                self.assertEqual(len(app_requests(seen)), 2)

    def test_reusable_policies_are_looked_up_by_id_once(self):
        apps = [api_app("Quiz Room", [f"{HOST}/quiz/*"], ["p-allow"]),
                api_app("Quiz Room (public)", [f"{HOST}/quiz"], [{"id": "p-allow"}])]
        seen = []
        code, out = run_check(apps, policies={"p-allow": {"id": "p-allow", "decision": "allow"}}, seen=seen)
        self.assertEqual(code, 0, out)
        self.assertEqual(policy_requests(seen), ["p-allow"])

    def test_reusable_bypass_policy_refuses(self):
        apps = [api_app("Quiz Room", QUIZ_URIS, ["p-bypass", "p-allow"])]
        policies = {"p-bypass": {"decision": "bypass"}, "p-allow": {"decision": "allow"}}
        code, out = run_check(apps, policies=policies)
        self.assertEqual(code, 1, out)
        self.assertIn("'Quiz Room', the most specific one covering", out)

    def test_policies_of_apps_outside_the_quiz_are_not_looked_up(self):
        apps = api_form(TODAY) + [api_app("status page", ["status.example.org/*"], ["p-elsewhere"])]
        seen = []
        code, out = run_check(apps, seen=seen)
        self.assertEqual(code, 0, out)
        self.assertEqual(policy_requests(seen), [])

    def test_legacy_domain_fields_are_read_without_destinations(self):
        legacy = {"name": "Quiz Room", "type": "self_hosted", "domain": f"{HOST}/quiz",
                  "self_hosted_domains": [f"{HOST}/quiz/*"], "policies": [{"decision": "allow"}]}
        code, out = run_check([legacy])
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
