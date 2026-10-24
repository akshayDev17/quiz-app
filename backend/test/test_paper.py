"""The point of the paper: an attempt outlives edits, archiving and deletion of its set.

Every test here is one of the scenarios that the old schema could not express —
it refused the admin action instead, or would have orphaned history if it had not.
"""

from __future__ import annotations

import unittest

import helpers  # noqa: F401  (sys.path)

from helpers import sample_import

from quiz_app import serializers
from quiz_app.auth import Identity  # noqa: F401  (kept for parity with other suites)
from quiz_app.clock import FakeClock
from quiz_app.d1.attempts import D1AttemptRepository
from quiz_app.d1.authoring import D1QuizAuthoring
from quiz_app.d1.catalog import D1Catalog, D1PaperSource
from quiz_app.d1.users import D1UserRepository
from quiz_app.errors import Conflict, Invalid, NotFound
from quiz_app.models import QuestionKey, User
from quiz_app.services.attempts import AttemptService
from quiz_app.services.authoring import AuthoringService

ADMIN = User("admin@example.com", "Admin", "admin")
ALICE = "alice@example.com"
START = 1_700_000_000_000
LIMIT_MS = 15 * 60 * 1000


def a_single_question_quiz() -> dict:
    """A complete rewrite of the quiz: one question, different everything."""
    return sample_import(
        difficulty="hard",
        questions=[{
            "prompt": "Replaced entirely",
            "explanation": "Because the author felt like it.",
            "points": 9,
            "options": [{"body": "a", "correct": True}, {"body": "b", "correct": False}],
        }],
    )


class PaperCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = helpers.fresh_db()
        self.clock = FakeClock(START)
        await D1UserRepository(self.db, self.clock).get_or_create(ADMIN.email)
        await D1UserRepository(self.db, self.clock).get_or_create(ALICE)
        self.authoring = AuthoringService(D1QuizAuthoring(self.db, self.clock), self.clock)
        self.catalog = D1Catalog(self.db)
        self.papers = D1PaperSource(self.db)
        self.repo = D1AttemptRepository(self.db)
        self.svc = AttemptService(self.catalog, self.papers, self.repo, self.clock)
        info = await self.authoring.import_set(ADMIN, sample_import())
        self.sid = info.id
        await self.authoring.publish(ADMIN, self.sid)

    async def start(self, email=ALICE) -> str:
        aid = (await self.svc.start_or_resume(email, self.sid)).attempt.id
        self.q1, self.q2, self.q3 = (await self.repo.answer_key(aid) + [None, None, None])[:3]
        return aid

    async def answered_and_submitted(self) -> str:
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.submit(ALICE, aid)
        return aid

    async def key_of_set(self, set_id) -> list[QuestionKey]:
        return [
            QuestionKey(q.id, q.points, frozenset(o.id for o in q.options if o.is_correct))
            for q in await self.papers.paper_source(set_id)
        ]


class EditTest(PaperCase):
    async def test_editing_a_played_set_is_allowed_and_invisible_to_old_attempts(self):
        aid = await self.answered_and_submitted()
        before = await self.svc.results(ALICE, aid)

        # The whole quiz is replaced under the attempt.
        await self.authoring.update(ADMIN, self.sid, a_single_question_quiz())

        after = await self.svc.results(ALICE, aid)
        self.assertEqual([q.prompt for q in after.questions], [q.prompt for q in before.questions])
        self.assertEqual(after.attempt.score, before.attempt.score)
        self.assertEqual(after.attempt.name, before.attempt.name)

    async def test_editing_while_paused_does_not_disturb_the_paper_or_the_answers(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.pause(ALICE, aid)

        await self.authoring.update(ADMIN, self.sid, a_single_question_quiz())

        resumed = await self.svc.resume(ALICE, aid)
        self.assertEqual(len(resumed.questions), 3)  # still the paper it started on
        self.assertEqual(resumed.selections[self.q1.question_id], frozenset(self.q1.correct))

        await self.svc.submit(ALICE, aid)
        self.assertEqual((await self.repo.get(aid)).score, 1)

    async def test_a_new_attempt_after_the_edit_gets_the_new_content(self):
        await self.answered_and_submitted()
        await self.authoring.update(ADMIN, self.sid, a_single_question_quiz())

        fresh = await self.start()
        session = await self.svc.session(ALICE, fresh)
        self.assertEqual([q.prompt for q in session.questions], ["Replaced entirely"])

    async def test_scoring_policy_is_pinned_at_start(self):
        # Graded by the rules in force when the attempt started, not when it ends.
        # Half of q2's two correct options scores 1.0 under `partial` and 0 under
        # `all_or_nothing`, so the score itself says which rule was applied.
        info = await self.authoring.import_set(ADMIN, sample_import(scoring_policy="partial"))
        await self.authoring.publish(ADMIN, info.id)
        aid = (await self.svc.start_or_resume(ALICE, info.id)).attempt.id
        half = (await self.repo.answer_key(aid))[1]
        await self.svc.save(ALICE, aid, half.question_id, list(half.correct)[:1])
        await self.svc.pause(ALICE, aid)

        await self.authoring.update(ADMIN, info.id, sample_import(scoring_policy="all_or_nothing"))

        await self.svc.resume(ALICE, aid)
        await self.svc.submit(ALICE, aid)
        attempt = await self.repo.get(aid)
        self.assertEqual(attempt.scoring_policy, "partial")
        self.assertEqual(attempt.score, 1.0)


class ArchiveTest(PaperCase):
    async def test_an_open_attempt_finishes_normally_after_archiving(self):
        aid = await self.start()
        await self.authoring.archive(ADMIN, self.sid)

        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        attempt = await self.svc.submit(ALICE, aid)

        self.assertEqual((attempt.status, attempt.score), ("submitted", 1))
        self.assertEqual(len((await self.svc.results(ALICE, aid)).questions), 3)

    async def test_an_open_attempt_resumes_after_archiving(self):
        aid = await self.start()
        await self.svc.pause(ALICE, aid)
        await self.authoring.archive(ADMIN, self.sid)

        # start_or_resume resumes an existing attempt without consulting the catalogue.
        resumed = await self.svc.start_or_resume(ALICE, self.sid)
        self.assertEqual(resumed.attempt.id, aid)
        self.assertEqual(len(resumed.questions), 3)

    async def test_starting_fresh_on_an_archived_set_is_still_refused(self):
        await self.authoring.archive(ADMIN, self.sid)
        with self.assertRaises(NotFound):
            await self.svc.start_or_resume(ALICE, self.sid)


class DeleteTest(PaperCase):
    async def test_delete_keeps_the_score_the_name_and_the_breakdown(self):
        aid = await self.answered_and_submitted()
        before = await self.svc.results(ALICE, aid)

        await self.authoring.delete(ADMIN, self.sid)

        after = await self.svc.results(ALICE, aid)
        self.assertIsNone(after.attempt.set_id)
        self.assertEqual(after.attempt.name, before.attempt.name)
        self.assertEqual(after.attempt.score, before.attempt.score)
        self.assertEqual(len(after.questions), len(before.questions))
        self.assertEqual(
            [(q.id, q.prompt) for q in after.questions], [(q.id, q.prompt) for q in before.questions]
        )
        self.assertEqual(
            {qid: r.awarded_points for qid, r in after.results.items()},
            {qid: r.awarded_points for qid, r in before.results.items()},
        )

        body = serializers.results(after)
        self.assertIsNone(body["set"]["id"])
        self.assertEqual(body["set"]["name"], before.attempt.name)
        self.assertEqual(len(body["questions"]), 3)

    async def test_delete_while_an_attempt_is_open_leaves_it_playable(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.pause(ALICE, aid)

        await self.authoring.delete(ADMIN, self.sid)

        resumed = await self.svc.resume(ALICE, aid)
        self.assertEqual(len(resumed.questions), 3)
        self.assertEqual(resumed.selections[self.q1.question_id], frozenset(self.q1.correct))

        await self.svc.save(ALICE, aid, self.q2.question_id, list(self.q2.correct))
        attempt = await self.svc.submit(ALICE, aid)
        self.assertEqual(attempt.status, "submitted")

        view = await self.svc.results(ALICE, aid)
        self.assertEqual(sum(1 for r in view.results.values() if r.is_correct), 2)

    async def test_history_after_delete_still_names_the_quiz(self):
        aid = await self.answered_and_submitted()
        name = (await self.repo.get(aid)).name
        await self.authoring.delete(ADMIN, self.sid)

        body = serializers.history(await self.svc.history(ALICE))
        self.assertEqual([(a["id"], a["set_id"], a["name"]) for a in body["attempts"]],
                         [(aid, None, name)])

    async def test_history_keeps_the_name_it_was_played_under_after_a_rename(self):
        aid = await self.answered_and_submitted()
        before = (await self.repo.get(aid)).name
        await self.authoring.update(ADMIN, self.sid, sample_import(title="Renamed later"))

        body = serializers.history(await self.svc.history(ALICE))
        self.assertEqual(body["attempts"][0]["name"], before)
        self.assertEqual((await self.repo.get(aid)).name, before)


class AtomicPauseTest(PaperCase):
    async def test_pause_stores_the_answers_it_carries(self):
        aid = await self.start()
        session = await self.svc.pause(
            ALICE, aid, {self.q1.question_id: frozenset(self.q1.correct)}
        )
        self.assertIsNotNone(session.attempt.paused_at)
        self.assertEqual(session.selections[self.q1.question_id], frozenset(self.q1.correct))
        self.assertEqual(await self.repo.selections(aid),
                         {self.q1.question_id: frozenset(self.q1.correct)})

    async def test_a_rejected_answer_leaves_the_attempt_unpaused_and_unwritten(self):
        aid = await self.start()
        other = await self.authoring.import_set(ADMIN, sample_import(difficulty="easy"))
        [foreign, *_] = await self.key_of_set(other.id)

        with self.assertRaises(Invalid):
            await self.svc.pause(ALICE, aid, {foreign.question_id: frozenset(foreign.correct)})

        attempt = await self.repo.get(aid)
        self.assertFalse(attempt.is_paused)
        self.assertEqual(await self.repo.selections(aid), {})

    async def test_pause_without_answers_still_freezes(self):
        aid = await self.start()
        self.assertIsNotNone((await self.svc.pause(ALICE, aid)).attempt.paused_at)

    async def test_pause_is_idempotent_and_keeps_late_answers(self):
        aid = await self.start()
        await self.svc.pause(ALICE, aid)
        frozen = (await self.repo.get(aid)).paused_at
        again = await self.svc.pause(ALICE, aid, {self.q1.question_id: frozenset(self.q1.correct)})
        self.assertEqual(again.attempt.paused_at, frozen)  # the clock was not re-frozen
        self.assertEqual(await self.repo.selections(aid),
                         {self.q1.question_id: frozenset(self.q1.correct)})

    async def test_untimed_attempts_still_refuse_to_pause(self):
        info = await self.authoring.import_set(ADMIN, sample_import(time_limit_minutes=None))
        await self.authoring.publish(ADMIN, info.id)
        aid = (await self.svc.start_or_resume(ALICE, info.id)).attempt.id
        with self.assertRaises(Conflict):
            await self.svc.pause(ALICE, aid)


if __name__ == "__main__":
    unittest.main()
