"""A set's visibility (public | private), end to end through the API.

Public: signed-out visitors can View it and signed-in solvers can take it (today's
behaviour, and the default). Private: absent from the public routes and from solvers'
/topics, and only its editors (admins) can start an attempt. Work already started on a
set that turns private is kept: an open attempt resumes and submits, results and
history stay.

Run:  python3 test/test_visibility.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import sample_import  # noqa: E402
from test_api import ADMIN, ALICE, BOB, ApiCase  # noqa: E402


def _set_ids(topics: dict) -> set[int]:
    return {c["id"] for t in topics["topics"] for g in t["groups"] for c in g["sets"]}


class VisibilityCase(ApiCase):
    async def make_private(self, sid: int) -> None:
        got = await self.ok("POST", f"/admin/sets/{sid}/visibility", {"visibility": "private"}, ADMIN)
        self.assertEqual(got, {"id": sid, "visibility": "private"})

    async def visibility_of(self, sid: int) -> str:
        return (await self.ok("GET", f"/admin/sets/{sid}", ident=ADMIN))["visibility"]


class SettingTest(VisibilityCase):
    async def test_new_sets_default_to_public(self):
        sid = await self.publish()
        self.assertEqual(await self.visibility_of(sid), "public")
        listed = (await self.ok("GET", "/admin/sets", ident=ADMIN))["sets"]
        self.assertEqual([s["visibility"] for s in listed], ["public"])

    async def test_an_import_can_choose_private(self):
        made = await self.ok("POST", "/admin/sets", sample_import(visibility="private"), ADMIN, 201)
        self.assertEqual(await self.visibility_of(made["id"]), "private")

    async def test_an_import_rejects_an_unknown_visibility(self):
        status, body = await self.call("POST", "/admin/sets", sample_import(visibility="hidden"), ADMIN)
        self.assertEqual((status, body), (422, {"error": "visibility must be one of public, private"}))

    async def test_the_toggle_flips_both_ways(self):
        sid = await self.publish()
        await self.make_private(sid)
        self.assertEqual(await self.visibility_of(sid), "private")
        got = await self.ok("POST", f"/admin/sets/{sid}/visibility", {"visibility": "public"}, ADMIN)
        self.assertEqual(got, {"id": sid, "visibility": "public"})
        self.assertEqual(await self.visibility_of(sid), "public")

    async def test_the_toggle_works_on_a_draft(self):
        made = await self.ok("POST", "/admin/sets", sample_import(), ADMIN, 201)
        await self.make_private(made["id"])
        self.assertEqual(await self.visibility_of(made["id"]), "private")

    async def test_the_toggle_validates_its_body(self):
        sid = await self.publish()
        for body in ({"visibility": "hidden"}, {}, None, ["private"]):
            status, _ = await self.call("POST", f"/admin/sets/{sid}/visibility", body, ADMIN)
            self.assertEqual(status, 422, body)
        self.assertEqual(await self.visibility_of(sid), "public")

    async def test_the_toggle_is_404_for_a_missing_set(self):
        status, _ = await self.call("POST", "/admin/sets/999/visibility", {"visibility": "private"}, ADMIN)
        self.assertEqual(status, 404)

    async def test_only_an_editor_may_set_visibility(self):
        sid = await self.publish()
        for body in ({"visibility": "private"}, {"visibility": "nonsense"}):
            got = await self.call("POST", f"/admin/sets/{sid}/visibility", body, ALICE)
            self.assertEqual(got, (403, {"error": "admin only"}))
        self.assertEqual(await self.visibility_of(sid), "public")

    async def test_an_edit_can_set_visibility(self):
        sid = await self.publish()
        body = {k: v for k, v in sample_import().items() if k not in ("topic", "subtopic")}
        await self.ok("PUT", f"/admin/sets/{sid}", {**body, "visibility": "private"}, ADMIN)
        self.assertEqual(await self.visibility_of(sid), "private")

    async def test_an_edit_without_visibility_keeps_it(self):
        # An editor that predates the field must never flip a private set to public.
        sid = await self.publish()
        await self.make_private(sid)
        body = {k: v for k, v in sample_import().items() if k not in ("topic", "subtopic")}
        await self.ok("PUT", f"/admin/sets/{sid}", body, ADMIN)
        self.assertEqual(await self.visibility_of(sid), "private")

    async def test_an_edit_rejects_an_unknown_visibility(self):
        sid = await self.publish()
        body = {k: v for k, v in sample_import().items() if k not in ("topic", "subtopic")}
        status, _ = await self.call("PUT", f"/admin/sets/{sid}", {**body, "visibility": "x"}, ADMIN)
        self.assertEqual(status, 422)
        self.assertEqual(await self.visibility_of(sid), "public")

    async def test_a_clone_keeps_visibility(self):
        sid = await self.publish()
        await self.make_private(sid)
        clone = await self.ok("POST", f"/admin/sets/{sid}/clone", None, ADMIN)
        self.assertEqual(await self.visibility_of(clone["id"]), "private")


class PrivateSetTest(VisibilityCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.public = await self.publish()
        self.private = await self.publish(title="Private set")
        await self.make_private(self.private)

    async def test_absent_from_the_public_list(self):
        topics = await self.ok("GET", "/public/topics", ident=None)
        self.assertEqual(_set_ids(topics), {self.public})

    async def test_public_view_is_404(self):
        self.assertEqual(
            await self.call("GET", f"/public/sets/{self.private}", ident=None),
            (404, {"error": "quiz set not found"}),
        )
        await self.ok("GET", f"/public/sets/{self.public}", ident=None)

    async def test_absent_from_a_solvers_topics(self):
        self.assertEqual(_set_ids(await self.ok("GET", "/topics")), {self.public})

    async def test_an_editor_still_sees_it_in_topics(self):
        self.assertEqual(_set_ids(await self.ok("GET", "/topics", ident=ADMIN)), {self.public, self.private})

    async def test_a_solver_cannot_open_or_start_it(self):
        self.assertEqual((await self.call("GET", f"/sets/{self.private}"))[0], 404)
        self.assertEqual(
            await self.call("POST", f"/sets/{self.private}/attempts"),
            (404, {"error": "quiz set not found"}),
        )
        self.assertEqual(await self.ok("GET", "/attempts"), {"attempts": []})

    async def test_an_editor_can_open_and_take_it(self):
        await self.ok("GET", f"/sets/{self.private}", ident=ADMIN)
        session = await self.start(self.private, ident=ADMIN)
        await self.ok("POST", f"/attempts/{session['attempt']['id']}/submit", None, ADMIN)

    async def test_a_draft_stays_invisible_even_when_public(self):
        made = await self.ok("POST", "/admin/sets", sample_import(title="Draft"), ADMIN, 201)
        self.assertNotIn(made["id"], _set_ids(await self.ok("GET", "/public/topics", ident=None)))
        self.assertNotIn(made["id"], _set_ids(await self.ok("GET", "/topics")))
        self.assertEqual((await self.call("GET", f"/public/sets/{made['id']}", ident=None))[0], 404)

    async def test_making_it_public_again_restores_everything(self):
        await self.ok("POST", f"/admin/sets/{self.private}/visibility", {"visibility": "public"}, ADMIN)
        self.assertIn(self.private, _set_ids(await self.ok("GET", "/public/topics", ident=None)))
        self.assertIn(self.private, _set_ids(await self.ok("GET", "/topics")))
        await self.start(self.private)


class StartedWorkTest(VisibilityCase):
    """A set that turns private refuses new attempts only; no one loses work."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.sid = await self.publish()

    async def test_an_open_attempt_resumes_answers_and_submits(self):
        session = await self.start(self.sid)
        aid = session["attempt"]["id"]
        await self.make_private(self.sid)

        # The intro stays reachable for the solver with the open attempt, so they can resume.
        intro = await self.ok("GET", f"/sets/{self.sid}")
        self.assertEqual(intro["open_attempt_id"], aid)
        resumed = await self.ok("POST", f"/sets/{self.sid}/attempts")  # 200: resumed, not created
        self.assertEqual(resumed["attempt"]["id"], aid)

        question = session["questions"][0]
        status, _ = await self.answer(aid, question["id"], [question["options"][0]["id"]])
        self.assertEqual(status, 204)
        submitted = await self.ok("POST", f"/attempts/{aid}/submit")
        self.assertEqual(submitted["status"], "submitted")
        await self.ok("GET", f"/attempts/{aid}/results")

        # Once that attempt is finished, the set is closed to them like any private set.
        self.assertEqual((await self.call("GET", f"/sets/{self.sid}"))[0], 404)
        self.assertEqual((await self.call("POST", f"/sets/{self.sid}/attempts"))[0], 404)

    async def test_finished_results_and_history_stay(self):
        aid = (await self.start(self.sid))["attempt"]["id"]
        await self.ok("POST", f"/attempts/{aid}/submit")
        await self.make_private(self.sid)

        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertEqual(results["attempt"]["id"], aid)
        history = await self.ok("GET", "/attempts")
        self.assertEqual([a["id"] for a in history["attempts"]], [aid])

    async def test_another_solvers_open_attempt_opens_nothing_for_me(self):
        await self.start(self.sid)  # Alice
        await self.make_private(self.sid)

        self.assertEqual((await self.call("GET", f"/sets/{self.sid}", ident=BOB))[0], 404)
        self.assertEqual((await self.call("POST", f"/sets/{self.sid}/attempts", ident=BOB))[0], 404)


if __name__ == "__main__":
    unittest.main()
