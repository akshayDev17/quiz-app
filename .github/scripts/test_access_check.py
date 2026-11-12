"""The deploy's Access check against fixture app lists.

Run: python3 .github/scripts/test_access_check.py
The fixtures mirror the live config read on 2026-11-12 and the planned change
in docs/adr/0009-signed-out-view-via-access-bypass.md, as the flat records
access_check.main() builds from the Cloudflare API.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from access_check import PROTECTED_PATHS, PUBLIC_PATHS, can_reach_quiz, find_problems, resolve  # noqa: E402

H = "akshayprabhakant.com"
PUBLIC = [f"{H}/quiz/view", f"{H}/quiz/view.txt", f"{H}/quiz/index.txt", f"{H}/quiz/_next/*", f"{H}/quiz/api/public/*"]


def app(name, uris, decisions, type="self_hosted"):
    return {"name": name, "type": type, "uris": uris, "decisions": decisions}


GRAPH = app("graph-notes (/graph)", [f"{H}/graph", f"{H}/graph/*"], ["allow"])
DESK = app("akshayprabhakant.com", [f"{H}/api/desk/*"], ["allow"])
# A Bypass elsewhere on the account never touches the quiz.
ELSEWHERE = app("status page", ["status.example.org/*"], ["bypass"])

TODAY = [
    app("akshayprabhakant.com", [f"{H}/quiz/*", f"{H}/quiz"], ["allow"]),
    GRAPH,
    DESK,
    ELSEWHERE,
]

# After step 1 of the change: the public app exists, /quiz still on the quiz app.
STEP_ONE = TODAY + [app("Quiz Room (public)", PUBLIC, ["bypass"])]

# After step 2: the bare /quiz moved to the public app.
PLANNED = [
    app("akshayprabhakant.com", [f"{H}/quiz/*"], ["allow"]),
    app("Quiz Room (public)", PUBLIC + [f"{H}/quiz"], ["bypass"]),
    GRAPH,
    DESK,
    ELSEWHERE,
]


def refusals(apps):
    return find_problems(apps)[0]


class Passes(unittest.TestCase):
    def test_todays_live_config(self):
        problems, notes = find_problems(TODAY)
        self.assertEqual(problems, [])
        self.assertIn(f"{H}/quiz: signed in only, by 'akshayprabhakant.com'.", notes)

    def test_step_one_of_the_change(self):
        self.assertEqual(refusals(STEP_ONE), [])

    def test_planned_config(self):
        problems, notes = find_problems(PLANNED)
        self.assertEqual(problems, [])
        for path in PUBLIC_PATHS:
            self.assertIn(f"{H}{path}: public, by the Bypass on 'Quiz Room (public)'.", notes)
        for path in PROTECTED_PATHS:
            self.assertIn(f"{H}{path}: signed in only, by 'akshayprabhakant.com'.", notes)

    def test_destination_spelling_is_normalized(self):
        apps = [app("Quiz", [f"https://{H.upper()}/quiz/", f"{H}/quiz/*"], ["allow"])]
        self.assertEqual(refusals(apps), [])


class Refuses(unittest.TestCase):
    def assertRefused(self, apps, *fragments):
        problems = refusals(apps)
        self.assertTrue(problems, "expected the deploy to be refused")
        for fragment in fragments:
            self.assertTrue(any(fragment in p for p in problems), f"{fragment!r} not in {problems}")

    def test_bypass_on_quiz_wildcard(self):
        apps = PLANNED + [app("open everything", [f"{H}/quiz/*"], ["bypass"])]
        self.assertRefused(apps, "'open everything' has a Bypass policy", f"{H}/quiz/*")

    def test_bypass_on_quiz_wildcard_on_the_public_app(self):
        apps = [app("akshayprabhakant.com", [f"{H}/quiz/*"], ["allow"]),
                app("Quiz Room (public)", PUBLIC + [f"{H}/quiz", f"{H}/quiz/*"], ["bypass"])]
        self.assertRefused(apps, f"outside the public allowlist: {H}/quiz/*",
                           f"most specific one covering {H}/quiz/set, has a Bypass policy")

    def test_bypass_app_also_holding_a_protected_page(self):
        apps = [a for a in PLANNED if a["name"] != "Quiz Room (public)"]
        apps.append(app("Quiz Room (public)", PUBLIC + [f"{H}/quiz", f"{H}/quiz/play"], ["bypass"]))
        self.assertRefused(apps, f"outside the public allowlist: {H}/quiz/play",
                           f"most specific one covering {H}/quiz/play, has a Bypass policy")

    def test_protected_path_with_no_allow_app(self):
        apps = [app("Quiz Room (public)", PUBLIC + [f"{H}/quiz"], ["bypass"]), GRAPH, DESK]
        self.assertRefused(apps, *(f"No Cloudflare Access self-hosted application covers {H}{p}." for p in PROTECTED_PATHS))

    def test_protected_path_whose_app_has_no_allow_policy(self):
        apps = PLANNED + [app("admin lockout", [f"{H}/quiz/admin"], ["deny"])]
        self.assertRefused(apps, f"'admin lockout', the most specific one covering {H}/quiz/admin, has no Allow policy")

    def test_bypass_and_allow_on_the_quiz_app(self):
        apps = [app("akshayprabhakant.com", [f"{H}/quiz/*", f"{H}/quiz"], ["allow", "bypass"])]
        self.assertRefused(apps, f"most specific one covering {H}/quiz/api/me, has a Bypass policy")

    def test_bypass_over_the_whole_host(self):
        # Loses on specificity to /quiz/*, but would expose the quiz the moment
        # the quiz app went away, so it may not exist at all.
        self.assertRefused(PLANNED + [app("site", [H], ["bypass"])], f"outside the public allowlist: {H}/*")

    def test_bypass_on_a_glob_reaching_into_the_quiz(self):
        self.assertRefused(PLANNED + [app("views", [f"{H}/quiz/view*"], ["bypass"])], f"{H}/quiz/view*")

    def test_public_app_also_holding_another_host(self):
        apps = [a for a in PLANNED if a["name"] != "Quiz Room (public)"]
        apps.append(app("Quiz Room (public)", PUBLIC + [f"{H}/quiz", "other.example.org/*"], ["bypass"]))
        self.assertRefused(apps, "other.example.org/*")

    def test_nothing_covers_the_quiz(self):
        self.assertRefused([GRAPH, DESK], f"No Cloudflare Access self-hosted application covers {H}/quiz.")

    def test_only_self_hosted_apps_protect(self):
        apps = [app("bookmark", [f"{H}/quiz", f"{H}/quiz/*"], ["allow"], type="bookmark")]
        self.assertRefused(apps, f"covers {H}/quiz/set.")


class Matching(unittest.TestCase):
    def test_exact_beats_wildcard_and_longer_beats_shorter(self):
        apps = [app("root", [f"{H}/*"], ["allow"]), app("quiz", [f"{H}/quiz/*"], ["allow"]),
                app("view", [f"{H}/quiz/view"], ["bypass"])]
        self.assertEqual([a["name"] for a in resolve(apps, "/quiz/set")], ["quiz"])
        self.assertEqual([a["name"] for a in resolve(apps, "/quiz/view")], ["view"])
        self.assertEqual([a["name"] for a in resolve(apps, "/quiz")], ["root"])

    def test_wildcard_does_not_cover_its_parent(self):
        self.assertEqual(resolve([app("quiz", [f"{H}/quiz/*"], ["allow"])], "/quiz"), [])

    def test_what_reaches_the_quiz(self):
        for uri in [f"{H}/quiz", f"{H}/quiz/*", f"{H}/quiz/view", f"{H}/*", H, f"{H}/q*", "*/quiz", f"{H}/quiz/"]:
            self.assertTrue(can_reach_quiz(uri), uri)
        for uri in [f"{H}/quizzes", f"{H}/graph/*", f"{H}/qui", f"www.{H}/quiz", f"*.{H}/quiz/*", "status.example.org/*"]:
            self.assertFalse(can_reach_quiz(uri), uri)


if __name__ == "__main__":
    unittest.main()
