"""The HTTP API over a fresh SQLite-backed D1: routes, status codes, wire shapes, answer secrecy.

Run:  python3 test/test_api.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "test"))

from helpers import fresh_db, sample_import  # noqa: E402

from quiz_app.api import MALFORMED, decode_body  # noqa: E402
from quiz_app.auth import Identity, parse_emails  # noqa: E402
from quiz_app.clock import FakeClock  # noqa: E402
from quiz_app.composition import build_api  # noqa: E402
from quiz_app.d1.catalog import D1AnswerKey  # noqa: E402

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

    async def key(self, sid):
        return await D1AnswerKey(self.db).answer_key(sid)

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
                "question_count": 3, "attempt_count": 0,
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

        q1, q2, q3 = await self.key(sid)
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
        self.assertEqual((results["attempt"]["score"], results["attempt"]["max_score"]), (3, 4))
        self.assertEqual(
            results["set"],
            {"id": sid, "name": card["name"], "topic": "RAG", "scoring_policy": "all_or_nothing", "reveal_answers": True},
        )
        first = results["questions"][0]
        self.assertEqual((first["points"], first["awarded_points"], first["is_correct"]), (1, 1, True))
        self.assertEqual(first["explanation"], "Vectors from different models are not comparable.")
        self.assertEqual(
            {o["id"] for o in first["options"] if o["correct"]}, set(q1.correct)
        )
        self.assertEqual({o["id"] for o in first["options"] if o["selected"]}, set(q1.correct))
        last_q = results["questions"][2]
        self.assertEqual((last_q["awarded_points"], last_q["is_correct"]), (0, False))
        self.assertTrue(all(not o["selected"] for o in last_q["options"]))

        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["last"], {"attempt_id": aid, "status": "submitted", "score": 3, "max_score": 4})
        self.assertIsNone(card["open_attempt"])

        intro = await self.ok("GET", f"/sets/{sid}")
        self.assertEqual(
            intro,
            {
                "id": sid, "topic": "RAG", "subtopic": "Embeddings and vector space", "name": card["name"],
                "description": None, "time_limit_minutes": 15, "question_count": 3,
                "max_attempts": None, "attempts_used": 1, "open_attempt_id": None,
            },
        )

        [row] = (await self.ok("GET", "/attempts"))["attempts"]
        self.assertEqual(
            row,
            {
                "id": aid, "set_id": sid, "name": card["name"], "topic": "RAG", "status": "submitted",
                "started_at": START, "finished_at": START, "score": 3, "max_score": 4,
            },
        )
        status, body = await self.answer(aid, q3.question_id, q3.correct)
        self.assertEqual((status, body), (409, {"error": "attempt finished"}))

    async def test_open_attempt_shows_on_card_and_intro(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        [card] = (await self.ok("GET", "/topics"))["topics"][0]["groups"][0]["sets"]
        self.assertEqual(card["open_attempt"], {"attempt_id": aid, "deadline_at": START + LIMIT_MS})
        self.assertEqual((await self.ok("GET", f"/sets/{sid}"))["open_attempt_id"], aid)

    async def test_answer_validation(self):
        sid = await self.publish()
        aid = (await self.start(sid))["attempt"]["id"]
        q1, q2, _ = await self.key(sid)
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
        q1, _, _ = await self.key(sid)
        await self.answer(aid, q1.question_id, q1.correct)
        self.clock.advance(LIMIT_MS)
        fetched = await self.ok("GET", f"/attempts/{aid}")
        self.assertEqual(fetched["attempt"]["status"], "expired")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertEqual(results["attempt"]["status"], "expired")
        self.assertEqual((results["attempt"]["score"], results["attempt"]["finished_at"]), (1, START + LIMIT_MS))
        [row] = (await self.ok("GET", "/attempts"))["attempts"]
        self.assertEqual(row["status"], "expired")

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
        q1, _, _ = await self.key(sid)
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
        q1, _, _ = await self.key(sid)
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
        q1, _, _ = await self.key(sid)
        await self.answer(aid, q1.question_id, q1.correct)
        await self.ok("POST", f"/attempts/{aid}/submit")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertFalse(results["set"]["reveal_answers"])
        for q in results["questions"]:
            self.assertIsNone(q["explanation"])
            self.assertTrue(all(o["correct"] is None for o in q["options"]))
        first = results["questions"][0]
        self.assertEqual((first["is_correct"], first["awarded_points"]), (True, 1))
        self.assertEqual({o["id"] for o in first["options"] if o["selected"]}, set(q1.correct))
        self.assertEqual(results["attempt"]["score"], 1)


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


if __name__ == "__main__":
    unittest.main()
