"""The HTTP API over a fresh SQLite-backed D1: routes, status codes, wire shapes, answer secrecy.

Run:  python3 test/test_api.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "test"))

from helpers import authored_key, fresh_db, sample_import  # noqa: E402

from quiz_app.api import MALFORMED, decode_body  # noqa: E402
from quiz_app.auth import CloudflareAccessIdentity, Identity, parse_emails  # noqa: E402
from quiz_app.clock import FakeClock  # noqa: E402
from quiz_app.composition import build_api  # noqa: E402

ADMIN = Identity("admin@example.com")
ALICE = Identity("alice@example.com")
BOB = Identity("bob@example.com")
START = 1_700_000_000_000
LIMIT_MS = 15 * 60_000
P = "/quiz/api"
SECRET_KEYS = ('"is_correct"', '"correct"', '"explanation"', '"awarded_points"')


class ApiCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = fresh_db()
        self.clock = FakeClock(START)
        self.api = build_api(self.db, [ADMIN.email], self.clock)

    async def call(self, method, path, body=None, ident=ALICE):
        return await self.api.handle(method, P + path, body, ident)

    async def ok(self, method, path, body=None, ident=ALICE, status=200):
        got, payload = await self.call(method, path, body, ident)
        self.assertEqual(got, status, payload)
        return payload

    async def publish(self, **overrides) -> int:
        made = await self.ok("POST", "/admin/sets", sample_import(**overrides), ADMIN, 201)
        await self.ok("POST", f"/admin/sets/{made['id']}/publish", None, ADMIN)
        return made["id"]

    async def start(self, sid, ident=ALICE) -> dict:
        return await self.ok("POST", f"/sets/{sid}/attempts", None, ident, 201)

    async def key(self, aid):
        """The paper's questions with their correct options, by paper id, in authored order."""
        return await authored_key(self.db, aid)

    async def answer(self, aid, qid, option_ids, ident=ALICE):
        return await self.call("PUT", f"/attempts/{aid}/answers/{qid}", {"option_ids": sorted(option_ids)}, ident)


class AuthAndMeTest(ApiCase):
    async def test_no_identity_401(self):
        status, body = await self.call("GET", "/topics", ident=None)
        self.assertEqual((status, body), (401, {"error": "sign-in required"}))

    async def test_paths_outside_the_api_are_404_even_anonymous(self):
        self.assertEqual((await self.api.handle("GET", "/quiz/admin", None, None))[0], 404)
        self.assertEqual((await self.api.handle("GET", "/other/me", None, ALICE))[0], 404)

    async def test_me_and_rename(self):
        self.assertEqual(
            await self.ok("GET", "/me"),
            {"email": "alice@example.com", "display_name": None, "role": "solver"},
        )
        renamed = await self.ok("PATCH", "/me", {"display_name": " A "})
        self.assertEqual(renamed["display_name"], "A")
        self.assertEqual((await self.ok("GET", "/me"))["display_name"], "A")
        for bad in ({"display_name": ""}, {"display_name": "x" * 61}, {"display_name": 5}, {}):
            self.assertEqual((await self.call("PATCH", "/me", bad))[0], 422, bad)
        self.assertEqual((await self.call("PATCH", "/me", ["x"]))[0], 422)

    async def test_admin_role_comes_from_admin_emails(self):
        self.assertEqual((await self.ok("GET", "/me", ident=ADMIN))["role"], "admin")

    async def test_every_route_upserts_the_user(self):
        await self.ok("GET", "/topics", ident=BOB)
        row = await self.db.prepare("SELECT email FROM users WHERE email = ?").bind(BOB.email).first()
        self.assertIsNotNone(row)

    async def test_solver_cannot_use_admin_routes(self):
        sid = await self.publish()
        calls = [
            ("GET", "/admin/sets", None),
            ("POST", "/admin/sets", sample_import()),
            ("POST", f"/admin/sets/{sid}/publish", None),
            ("POST", f"/admin/sets/{sid}/archive", None),
            ("POST", f"/admin/sets/{sid}/clone", None),
        ]
        for method, path, body in calls:
            status, payload = await self.call(method, path, body, ALICE)
            self.assertEqual((status, payload), (403, {"error": "admin only"}), path)

    async def test_unknown_route_404_and_bad_json_422(self):
        self.assertEqual(await self.call("GET", "/nope"), (404, {"error": "not found"}))
        self.assertEqual((await self.call("DELETE", "/me"))[0], 404)
        self.assertEqual((await self.call("GET", "/sets/abc"))[0], 404)
        self.assertEqual((await self.call("GET", "/sets/1/attempts"))[0], 404)
        self.assertEqual((await self.call("PATCH", "/me", MALFORMED))[0], 422)
        self.assertEqual((await self.call("POST", "/admin/sets", MALFORMED, ADMIN))[0], 422)
        self.assertEqual((await self.call("POST", "/admin/sets", [1], ADMIN))[0], 422)
        self.assertEqual((await self.call("POST", "/admin/sets", {"topic": 1}, ADMIN))[0], 422)

    async def test_trailing_slash_is_ignored(self):
        self.assertEqual((await self.call("GET", "/me/"))[0], 200)

    async def test_decode_body(self):
        self.assertIsNone(decode_body(None))
        self.assertIsNone(decode_body("  "))
        self.assertEqual(decode_body('{"a": 1}'), {"a": 1})
        self.assertIs(decode_body("{nope"), MALFORMED)

    async def test_cloudflare_access_fails_closed_when_get_identity_raises(self):
        class _Access:
            async def getIdentity(self):
                raise RuntimeError("Access lookup failed")

        provider = CloudflareAccessIdentity(SimpleNamespace(access=_Access()), retry_delay_s=0, log=lambda _: None)
        self.assertIsNone(await provider.identify(None))

    async def test_cloudflare_access_fails_closed_on_an_unreadable_identity(self):
        class _Identity:
            @property
            def email(self):
                raise RuntimeError("proxy gone")

        class _Access:
            async def getIdentity(self):
                return _Identity()

        provider = CloudflareAccessIdentity(SimpleNamespace(access=_Access()), retry_delay_s=0, log=lambda _: None)
        self.assertIsNone(await provider.identify(None))

    def test_parse_emails(self):
        self.assertEqual(parse_emails(" A@x.com, ,b@Y.com,"), frozenset({"a@x.com", "b@y.com"}))
        self.assertEqual(parse_emails(None), frozenset())
        self.assertEqual(parse_emails(""), frozenset())


class AdminTest(ApiCase):
    async def test_import_publish_clone_archive_list(self):
        made = await self.ok("POST", "/admin/sets", sample_import(), ADMIN, 201)
        self.assertEqual(made["name"], "Embeddings and vector space · Set 1")
        listed = await self.ok("GET", "/admin/sets", ident=ADMIN)
        self.assertEqual(
            listed["sets"],
            [{
                "id": made["id"], "topic": "RAG", "name": made["name"], "status": "draft",
                "visibility": "public", "question_count": 3, "attempt_count": 0,
            }],
        )
        self.assertEqual(await self.ok("POST", f"/admin/sets/{made['id']}/publish", ident=ADMIN),
                         {"id": made["id"], "status": "published"})
        clone = await self.ok("POST", f"/admin/sets/{made['id']}/clone", ident=ADMIN)
        self.assertEqual(clone["status"], "draft")
        self.assertNotEqual(clone["id"], made["id"])
        self.assertEqual(await self.ok("POST", f"/admin/sets/{made['id']}/archive", ident=ADMIN),
                         {"id": made["id"], "status": "archived"})

    async def test_missing_set_404(self):
        for action in ("publish", "archive", "clone"):
            self.assertEqual((await self.call("POST", f"/admin/sets/999/{action}", None, ADMIN))[0], 404)


class FlowTest(ApiCase):
    async def test_full_flow(self):
        sid = await self.publish()
        topics = await self.ok("GET", "/topics")
        self.assertEqual(len(topics["topics"]), 1)
        [group] = topics["topics"][0]["groups"]
        [card] = group["sets"]
        self.assertEqual(group["subtopic"]["name"], "Embeddings and vector space")
        self.assertEqual(
            (card["id"], card["short_name"], card["question_count"], card["last"], card["open_attempt"]),
            (sid, "Set 1", 3, None, None),
        )

        started = await self.start(sid)
        aid = started["attempt"]["id"]
        self.assertEqual(started["attempt"]["deadline_at"], START + LIMIT_MS)
        self.assertEqual(started["server_now"], START)
        self.assertEqual(started["set"], {"name": card["name"], "topic": "RAG", "subtopic": "Embeddings and vector space"})
        resumed = await self.ok("POST", f"/sets/{sid}/attempts")
        self.assertEqual(resumed["attempt"]["id"], aid)

        q1, q2, q3 = await self.key(aid)
        status, body = await self.answer(aid, q1.question_id, q1.correct)
        self.assertEqual((status, body), (204, None))
        await self.answer(aid, q2.question_id, q2.correct)
        again = await self.ok("GET", f"/attempts/{aid}")
        self.assertEqual(again["selections"][str(q1.question_id)], sorted(q1.correct))
        self.assertTrue(all(isinstance(k, str) for k in again["selections"]))

        self.assertEqual(await self.call("GET", f"/attempts/{aid}/results"), (409, {"error": "attempt in progress"}))
        self.assertEqual(await self.ok("POST", f"/attempts/{aid}/submit"), {"attempt_id": aid, "status": "submitted"})
        self.assertEqual(await self.ok("POST", f"/attempts/{aid}/submit"), {"attempt_id": aid, "status": "submitted"})

        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertEqual(results["attempt"]["status"], "submitted")
        # +2 per correct tick: q1 3 x 2 + q2 2 x 2, and q3 left blank costs 2. Max = 2 x 6 correct options.
        self.assertEqual((results["attempt"]["score"], results["attempt"]["max_score"]), (8, 12))
        self.assertEqual(
            results["set"],
            {"id": sid, "name": card["name"], "topic": "RAG", "scoring_policy": "negative_marking", "reveal_answers": True},
        )
        served = {q["id"]: q for q in results["questions"]}
        first = served[q1.question_id]
        self.assertEqual((first["points"], first["awarded_points"], first["is_correct"]), (6, 6, True))
        self.assertEqual(first["explanation"], "Vectors from different models are not comparable.")
        self.assertEqual(
            {o["id"] for o in first["options"] if o["correct"]}, set(q1.correct)
        )
        self.assertEqual({o["id"] for o in first["options"] if o["selected"]}, set(q1.correct))
        last_q = served[q3.question_id]
        self.assertEqual((last_q["awarded_points"], last_q["is_correct"]), (-2, False))
        self.assertTrue(all(not o["selected"] for o in last_q["options"]))

        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["last"], {"attempt_id": aid, "status": "submitted", "score": 8, "max_score": 12})
        self.assertIsNone(card["open_attempt"])

        intro = await self.ok("GET", f"/sets/{sid}")
        self.assertEqual(
            intro,
            {
                "id": sid, "topic": "RAG", "subtopic": "Embeddings and vector space", "name": card["name"],
                "description": None, "time_limit_minutes": 15, "question_count": 3,
                "subjective_count": 0, "max_attempts": None, "attempts_used": 1, "open_attempt_id": None,
            },
        )

        [row] = (await self.ok("GET", "/attempts"))["attempts"]
        self.assertEqual(
            row,
            {
                "id": aid, "set_id": sid, "name": card["name"], "topic": "RAG", "status": "submitted",
                "started_at": START, "finished_at": START, "score": 8, "max_score": 12,
                "awaiting_count": 0,
            },
        )
        status, body = await self.answer(aid, q3.question_id, q3.correct)
        self.assertEqual((status, body), (409, {"error": "attempt finished"}))

    async def test_open_attempt_shows_on_card_and_intro(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["open_attempt"], {"attempt_id": aid, "remaining_ms": LIMIT_MS})
        self.assertEqual((await self.ok("GET", f"/sets/{sid}"))["open_attempt_id"], aid)

    async def test_a_paused_attempt_shows_the_time_it_was_frozen_at(self):
        # The card used to derive this from deadline_at, which for a paused attempt is
        # already in the past — it showed "00:00 left" on an attempt with 14:30 left.
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        self.clock.advance(30_000)
        await self.ok("POST", f"/attempts/{aid}/pause", None)
        self.clock.advance(LIMIT_MS * 2)          # paused far past the deadline

        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["open_attempt"]["remaining_ms"], LIMIT_MS - 30_000)

        # ...and the time is still there when they come back.
        resumed = await self.ok("POST", f"/attempts/{aid}/resume")
        self.assertEqual(resumed["attempt"]["paused_at"], None)

    async def test_answer_validation(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, q2, _ = await self.key(aid)
        for bad in (None, {}, {"option_ids": "x"}, {"option_ids": [1.5]}, {"option_ids": [True]}, [1]):
            status, _ = await self.call("PUT", f"/attempts/{aid}/answers/{q1.question_id}", bad)
            self.assertEqual(status, 422, bad)
        status, _ = await self.answer(aid, q1.question_id, q2.correct)
        self.assertEqual(status, 422)
        status, _ = await self.answer(aid, 999_999, [1])
        self.assertEqual(status, 422)

    async def test_unpublished_set_is_404_for_solvers(self):
        made = await self.ok("POST", "/admin/sets", sample_import(), ADMIN, 201)
        self.assertEqual((await self.call("GET", f"/sets/{made['id']}"))[0], 404)
        self.assertEqual((await self.call("POST", f"/sets/{made['id']}/attempts"))[0], 404)
        self.assertEqual((await self.ok("GET", "/topics"))["topics"], [])

    async def test_max_attempts_409(self):
        sid = await self.publish(max_attempts=1)
        aid = (await self.start(sid))["attempt"]["id"]
        await self.ok("POST", f"/attempts/{aid}/submit")
        status, body = await self.call("POST", f"/sets/{sid}/attempts")
        self.assertEqual((status, body), (409, {"error": "no attempts left"}))

    async def test_timeout_flow(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, _, _ = await self.key(aid)
        await self.answer(aid, q1.question_id, q1.correct)
        self.clock.advance(LIMIT_MS)
        fetched = await self.ok("GET", f"/attempts/{aid}")
        self.assertEqual(fetched["attempt"]["status"], "expired")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertEqual(results["attempt"]["status"], "expired")
        self.assertEqual((results["attempt"]["score"], results["attempt"]["finished_at"]), (2, START + LIMIT_MS))  # 6 - 2 - 2
        [row] = (await self.ok("GET", "/attempts"))["attempts"]
        self.assertEqual(row["status"], "expired")

    async def test_pause_carries_the_pending_answers(self):
        # The browser's unsaved answers ride along with the pause, so the freeze and
        # the answers commit together and nothing is lost behind the paused state.
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, q2, _ = await self.key(aid)

        paused = await self.ok("POST", f"/attempts/{aid}/pause", {"answers": [
            {"question_id": q1.question_id, "option_ids": sorted(q1.correct)},
            {"question_id": q2.question_id, "option_ids": sorted(q2.correct)},
        ]})

        self.assertIsNotNone(paused["attempt"]["paused_at"])
        self.assertEqual(paused["selections"][str(q1.question_id)], sorted(q1.correct))
        self.assertEqual(paused["selections"][str(q2.question_id)], sorted(q2.correct))

        # A write that arrives after the freeze is still refused.
        self.assertEqual(await self.call("PUT", f"/attempts/{aid}/answers/{q1.question_id}",
                                         {"option_ids": []}), (409, {"error": "attempt paused"}))

    async def test_pause_with_a_bad_answer_is_rejected_and_does_not_freeze(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, q2, _ = await self.key(aid)

        status, _ = await self.call("POST", f"/attempts/{aid}/pause", {"answers": [
            {"question_id": q1.question_id, "option_ids": sorted(q2.correct)},  # wrong question's options
        ]})
        self.assertEqual(status, 422)

        session = await self.ok("GET", f"/attempts/{aid}")
        self.assertIsNone(session["attempt"]["paused_at"])
        self.assertEqual(session["selections"], {})

    async def test_pause_without_a_body_still_freezes(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        paused = await self.ok("POST", f"/attempts/{aid}/pause", None)
        self.assertIsNotNone(paused["attempt"]["paused_at"])

    async def test_topics_runs_lazy_expiry(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        self.clock.advance(LIMIT_MS)
        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertIsNone(card["open_attempt"])
        self.assertEqual((card["last"]["attempt_id"], card["last"]["status"]), (aid, "expired"))


class SecrecyTest(ApiCase):
    async def test_no_answer_leak_before_finish(self):
        sid = await self.publish()
        other = await self.publish()
        started = await self.start(sid)
        aid = started["attempt"]["id"]
        q1, _, _ = await self.key(aid)
        await self.answer(aid, q1.question_id, q1.correct)
        bodies = [
            await self.ok("GET", "/topics"),
            await self.ok("GET", f"/sets/{sid}"),
            await self.ok("GET", f"/sets/{other}"),
            started,
            await self.ok("POST", f"/sets/{sid}/attempts"),
            await self.ok("GET", f"/attempts/{aid}"),
            await self.ok("GET", "/attempts"),
        ]
        for body in bodies:
            text = json.dumps(body)
            for key in SECRET_KEYS:
                self.assertNotIn(key, text)
            self.assertNotIn('"score": ', text.replace('"score": null', ""))
            self.assertNotIn('"max_score": ', text.replace('"max_score": null', ""))
        [row] = (await self.ok("GET", "/attempts"))["attempts"]
        self.assertEqual((row["score"], row["max_score"], row["finished_at"]), (None, None, None))

    async def test_foreign_attempt_is_404_everywhere(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, _, _ = await self.key(aid)
        mine_before = await self.ok("GET", f"/attempts/{aid}")
        probes = [
            ("GET", f"/attempts/{aid}", None),
            ("PUT", f"/attempts/{aid}/answers/{q1.question_id}", {"option_ids": sorted(q1.correct)}),
            ("POST", f"/attempts/{aid}/submit", None),
            ("GET", f"/attempts/{aid}/results", None),
        ]
        for method, path, body in probes:
            self.assertEqual(await self.call(method, path, body, BOB), (404, {"error": "attempt not found"}), path)
        self.assertEqual(await self.ok("GET", f"/attempts/{aid}"), mine_before)
        self.assertEqual((await self.ok("GET", "/attempts", ident=BOB))["attempts"], [])
        self.assertEqual((await self.call("GET", "/attempts/doesnotexist"))[0], 404)

    async def test_reveal_answers_false_hides_correct_and_explanation(self):
        sid = await self.publish(reveal_answers=False)
        aid = (await self.start(sid))["attempt"]["id"]
        q1, q2, q3 = await self.key(aid)
        await self.answer(aid, q1.question_id, q1.correct)
        await self.ok("POST", f"/attempts/{aid}/submit")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertFalse(results["set"]["reveal_answers"])
        for q in results["questions"]:
            self.assertIsNone(q["explanation"])
            self.assertTrue(all(o["correct"] is None for o in q["options"]))
        served = {q["id"]: q for q in results["questions"]}
        first = served[q1.question_id]
        self.assertEqual((first["is_correct"], first["awarded_points"]), (True, 6))
        self.assertEqual([served[k.question_id]["points"] for k in (q1, q2, q3)], [6, 4, 2])
        self.assertEqual(results["attempt"]["max_score"], 12)
        self.assertEqual({o["id"] for o in first["options"] if o["selected"]}, set(q1.correct))
        self.assertEqual(results["attempt"]["score"], 2)  # 6, then two blanks at -2


class TopicsOrderTest(ApiCase):
    async def test_topics_grouping_order(self):
        def spec(topic, subtopic):
            kw = {"topic": {"slug": topic.lower(), "name": topic}}
            kw["subtopic"] = {"slug": subtopic.lower(), "name": subtopic} if subtopic else None
            return kw

        # Imported out of display order; topic/subtopic positions follow first appearance.
        a1 = await self.publish(**spec("Alpha", "Zeta"))
        a2 = await self.publish(**spec("Alpha", None))
        a3 = await self.publish(**spec("Alpha", "Beta"))
        a4 = await self.publish(**spec("Alpha", "Zeta"))
        b1 = await self.publish(**spec("Bravo", None))
        topics = (await self.ok("GET", "/topics"))["topics"]
        self.assertEqual([t["name"] for t in topics], ["Alpha", "Bravo"])
        alpha = topics[0]["groups"]
        self.assertEqual([g["subtopic"] and g["subtopic"]["name"] for g in alpha], [None, "Zeta", "Beta"])
        self.assertEqual([[c["id"] for c in g["sets"]] for g in alpha], [[a2], [a1, a4], [a3]])
        self.assertEqual([[c["id"] for c in g["sets"]] for g in topics[1]["groups"]], [[b1]])

    async def test_short_name_drops_subtopic_keeps_difficulty_and_style(self):
        await self.publish(difficulty="hard", style="scenario")
        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["short_name"], "Hard · Scenario · Set 1")
        self.assertEqual((card["difficulty"], card["style"]), ("hard", "scenario"))


#: One concrete request per signed-in route. Any route added to ``Api`` without a row here
#: fails ``test_every_route_has_an_anonymous_probe``.
SIGNED_IN_PROBES = [
    ("GET", "/me"),
    ("PATCH", "/me"),
    ("GET", "/topics"),
    ("GET", "/sets/1"),
    ("POST", "/sets/1/attempts"),
    ("GET", "/attempts"),
    ("GET", "/attempts/abc"),
    ("PUT", "/attempts/abc/answers/1"),
    ("POST", "/attempts/abc/submit"),
    ("POST", "/attempts/abc/pause"),
    ("POST", "/attempts/abc/resume"),
    ("GET", "/attempts/abc/results"),
    ("GET", "/admin/sets"),
    ("POST", "/admin/sets"),
    ("GET", "/admin/sets/1"),
    ("PUT", "/admin/sets/1"),
    ("POST", "/admin/sets/1/publish"),
    ("POST", "/admin/sets/1/archive"),
    ("POST", "/admin/sets/1/visibility"),
    ("POST", "/admin/sets/1/clone"),
    ("DELETE", "/admin/sets/1"),
    ("GET", "/admin/evaluators"),
    ("POST", "/admin/evaluators"),
    ("POST", "/admin/evaluators/order"),
    ("PUT", "/admin/evaluators/1"),
    ("DELETE", "/admin/evaluators/1"),
    ("POST", "/admin/evaluations/rerun"),
]

#: Keys that belong to a person or an attempt; none may appear in a public payload.
PERSONAL_KEYS = ("email", "score", "max_score", "last", "open_attempt", "attempt_id", "attempts_used")


def _keys(value) -> set[str]:
    """Every dict key anywhere in a JSON-shaped value."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


class AnonymousTest(ApiCase):
    async def test_every_route_has_an_anonymous_probe(self):
        registered = {(m, p.pattern) for m, p, _ in self.api._routes}
        probed = {
            (m, p.pattern)
            for m, p, _ in self.api._routes
            for method, path in SIGNED_IN_PROBES
            if m == method and p.match(path)
        }
        self.assertEqual(registered - probed, set())

    async def test_every_signed_in_route_is_401_without_an_identity(self):
        sid = await self.publish()
        for method, path in SIGNED_IN_PROBES:
            path = path.replace("/1", f"/{sid}", 1) if path.startswith(("/sets/", "/admin/sets/")) else path
            got = await self.call(method, path, {}, ident=None)
            self.assertEqual(got, (401, {"error": "sign-in required"}), f"{method} {path}")
        self.assertEqual(await self.users(), 1)  # only the admin who published

    async def users(self) -> int:
        return (await self.db.prepare("SELECT COUNT(*) AS n FROM users").first())["n"]


class PublicTest(ApiCase):
    async def test_topics_are_todays_cards_without_a_solvers_data(self):
        sid = await self.publish()
        draft = (await self.ok("POST", "/admin/sets", sample_import(difficulty="hard"), ADMIN, 201))["id"]
        await self.start(sid)  # alice has an open attempt
        signed_in = await self.ok("GET", "/topics")
        self.assertIsNotNone(signed_in["topics"][0]["groups"][0]["sets"][0]["open_attempt"])
        public = await self.ok("GET", "/public/topics", ident=None)

        for topic in signed_in["topics"]:
            for group in topic["groups"]:
                for card in group["sets"]:
                    del card["last"], card["open_attempt"]
        self.assertEqual(public, signed_in)
        ids = [c["id"] for t in public["topics"] for g in t["groups"] for c in g["sets"]]
        self.assertEqual(ids, [sid])
        self.assertNotIn(draft, ids)

    async def test_set_is_the_authored_key_in_order_without_points(self):
        sid = await self.publish(shuffle_questions=True, shuffle_options=True)
        view = await self.ok("GET", f"/public/sets/{sid}", ident=None)
        authored = sample_import()["questions"]
        self.assertEqual(
            view["set"],
            {
                "id": sid, "name": "Embeddings and vector space · Set 1", "topic": "RAG",
                "subtopic": "Embeddings and vector space", "description": None,
                "time_limit_minutes": 15, "question_count": 3, "reveal_answers": True,
            },
        )
        self.assertEqual([q["prompt"] for q in view["questions"]], [q["prompt"] for q in authored])
        for got, want in zip(view["questions"], authored):
            self.assertEqual(set(got), {"id", "kind", "prompt", "explanation", "model_answer", "options"})
            self.assertEqual((got["kind"], got["model_answer"]), ("choice", None))
            self.assertEqual(got["explanation"], want["explanation"])
            self.assertEqual([(o["body"], o["correct"]) for o in got["options"]],
                             [(o["body"], o["correct"]) for o in want["options"]])

    async def test_reveal_answers_false_hides_the_key_and_explanations(self):
        sid = await self.publish(reveal_answers=False)
        view = await self.ok("GET", f"/public/sets/{sid}", ident=None)
        self.assertFalse(view["set"]["reveal_answers"])
        for q in view["questions"]:
            self.assertIsNone(q["explanation"])
            self.assertTrue(q["options"])
            self.assertTrue(all(o["correct"] is None for o in q["options"]))

    async def test_drafts_archived_and_missing_sets_are_404(self):
        draft = (await self.ok("POST", "/admin/sets", sample_import(), ADMIN, 201))["id"]
        archived = await self.publish(difficulty="hard")
        await self.ok("POST", f"/admin/sets/{archived}/archive", None, ADMIN)
        for sid in (draft, archived, 999):
            self.assertEqual(
                await self.call("GET", f"/public/sets/{sid}", ident=None),
                (404, {"error": "quiz set not found"}),
            )
        self.assertEqual((await self.call("GET", "/public/sets/abc", ident=None))[0], 404)
        self.assertEqual((await self.call("GET", "/public", ident=None))[0], 404)
        self.assertEqual((await self.call("GET", "/public/me", ident=None))[0], 404)

    async def test_only_get_is_allowed(self):
        sid = await self.publish()
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD"):
            for path in ("/public/topics", f"/public/sets/{sid}", "/public/nope"):
                got = await self.call(method, path, {}, ident=None)
                self.assertEqual(got, (405, {"error": "method not allowed"}), f"{method} {path}")

    async def test_public_routes_never_create_or_read_a_user(self):
        sid = await self.publish()
        for ident in (None, BOB):
            await self.ok("GET", "/public/topics", ident=ident)
            await self.ok("GET", f"/public/sets/{sid}", ident=ident)
        self.assertEqual((await self.db.prepare("SELECT COUNT(*) AS n FROM users").first())["n"], 1)

    async def test_public_payloads_carry_nothing_of_a_person(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        await self.ok("POST", f"/attempts/{aid}/submit")
        await self.start(await self.publish(difficulty="hard"))  # and one still open
        for path in ("/public/topics", f"/public/sets/{sid}"):
            payload = await self.ok("GET", path, ident=None)
            self.assertEqual(_keys(payload) & set(PERSONAL_KEYS), set(), path)
            text = json.dumps(payload)
            self.assertNotIn("@example.com", text, path)
            self.assertNotIn(aid, text, path)

    def test_response_headers(self):
        from quiz_app.api import response_headers

        self.assertEqual(response_headers(f"{P}/public/topics", 200), {"cache-control": "public, max-age=60"})
        self.assertEqual(response_headers(f"{P}/public/sets/1/", 200), {"cache-control": "public, max-age=60"})
        self.assertEqual(response_headers(f"{P}/public/sets/1", 404), {})
        self.assertEqual(response_headers(f"{P}/public/topics", 405), {"allow": "GET"})
        self.assertEqual(response_headers(f"{P}/topics", 200), {})
        self.assertEqual(response_headers(f"{P}/publicity", 200), {})


if __name__ == "__main__":
    unittest.main()
