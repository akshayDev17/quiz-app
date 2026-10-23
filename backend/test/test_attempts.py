"""Attempt lifecycle: start/resume, autosave, submit, lazy expiry, grading.

Run:  python3 test/test_attempts.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "test"))

from helpers import fresh_db, sample_import  # noqa: E402

from quiz_app.clock import FakeClock  # noqa: E402
from quiz_app.d1.attempts import D1AttemptRepository  # noqa: E402
from quiz_app.d1.authoring import D1QuizAuthoring  # noqa: E402
from quiz_app.d1.catalog import D1AnswerKey, D1Catalog  # noqa: E402
from quiz_app.d1.users import D1UserRepository  # noqa: E402
from quiz_app.errors import Conflict, Invalid, NotFound  # noqa: E402
from quiz_app.models import GradeResult, QuestionResult, User  # noqa: E402
from quiz_app.services.attempts import AttemptService  # noqa: E402
from quiz_app.services.authoring import AuthoringService  # noqa: E402
from quiz_app.shuffle import display_order  # noqa: E402

ADMIN = User("admin@example.com", "Admin", "admin")
ALICE = "alice@example.com"
BOB = "bob@example.com"
START = 1_700_000_000_000
LIMIT_MS = 15 * 60_000


class _OpenForMissesOnce(D1AttemptRepository):
    """Simulates the race: another request opened an attempt after our ``open_for`` check."""

    def __init__(self, db):
        super().__init__(db)
        self.missed = False

    async def open_for(self, set_id, email):
        if not self.missed:
            self.missed = True
            return None
        return await super().open_for(set_id, email)


class AttemptCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = fresh_db()
        self.clock = FakeClock(START)
        users = D1UserRepository(self.db, self.clock)
        for email in (ADMIN.email, ALICE, BOB):
            await users.get_or_create(email)
        self.authoring = AuthoringService(D1QuizAuthoring(self.db, self.clock), self.clock)
        self.catalog = D1Catalog(self.db)
        self.keys = D1AnswerKey(self.db)
        self.repo = D1AttemptRepository(self.db)
        self.svc = self.service(self.repo)
        self.sid = await self.seed()
        self.q1, self.q2, self.q3 = await self.keys.answer_key(self.sid)

    def service(self, repo):
        return AttemptService(self.catalog, self.keys, repo, self.clock)

    async def seed(self, publish=True, **overrides) -> int:
        info = await self.authoring.import_set(ADMIN, sample_import(**overrides))
        if publish:
            await self.authoring.publish(ADMIN, info.id)
        return info.id

    async def start(self, email=ALICE, set_id=None) -> str:
        return (await self.svc.start_or_resume(email, set_id or self.sid)).attempt.id

    async def count_results(self, attempt_id) -> int:
        row = await self.db.prepare(
            "SELECT COUNT(*) AS n FROM attempt_results WHERE attempt_id = ?"
        ).bind(attempt_id).first()
        return row["n"]


class StartTest(AttemptCase):
    async def test_start_then_start_again_resumes(self):
        a = await self.svc.start_or_resume(ALICE, self.sid)
        b = await self.svc.start_or_resume(ALICE, self.sid)
        self.assertEqual(a.attempt.id, b.attempt.id)
        self.assertTrue(a.created)
        self.assertFalse(b.created)
        self.assertEqual(len(a.attempt.id), 32)  # uuid4().hex

    async def test_concurrent_start_returns_same_attempt(self):
        a, b = await asyncio.gather(
            self.svc.start_or_resume(ALICE, self.sid), self.svc.start_or_resume(ALICE, self.sid)
        )
        self.assertEqual(a.attempt.id, b.attempt.id)

    async def test_start_race_on_unique_index_returns_existing_attempt(self):
        existing = await self.start()
        racing = self.service(_OpenForMissesOnce(self.db))
        session = await racing.start_or_resume(ALICE, self.sid)
        self.assertEqual(session.attempt.id, existing)
        self.assertFalse(session.created)

    async def test_deadline_is_start_plus_limit(self):
        session = await self.svc.start_or_resume(ALICE, self.sid)
        self.assertEqual(session.attempt.started_at, START)
        self.assertEqual(session.attempt.deadline_at, START + LIMIT_MS)
        self.assertEqual(session.server_now, START)
        self.assertEqual(session.attempt.status, "in_progress")

    async def test_session_carries_questions_and_selections(self):
        session = await self.svc.start_or_resume(ALICE, self.sid)
        self.assertEqual([q.id for q in session.questions], [self.q1.question_id, self.q2.question_id, self.q3.question_id])
        self.assertEqual(session.selections, {})
        self.assertEqual(session.set.id, self.sid)

    async def test_untimed_set_has_no_deadline_and_never_expires(self):
        sid = await self.seed(time_limit_minutes=None)
        aid = await self.start(set_id=sid)
        self.clock.advance(10 * 24 * 3_600_000)
        session = await self.svc.session(ALICE, aid)
        self.assertIsNone(session.attempt.deadline_at)
        self.assertEqual(session.attempt.status, "in_progress")
        await self.svc.expire_due_for(ALICE)
        self.assertEqual((await self.svc.session(ALICE, aid)).attempt.status, "in_progress")

    async def test_max_attempts(self):
        sid = await self.seed(max_attempts=1)
        aid = await self.start(set_id=sid)
        self.assertEqual(await self.start(set_id=sid), aid)  # resuming the open one is fine
        await self.svc.submit(ALICE, aid)
        with self.assertRaises(Conflict) as caught:
            await self.svc.start_or_resume(ALICE, sid)
        self.assertEqual(caught.exception.message, "no attempts left")
        await self.svc.start_or_resume(BOB, sid)  # the limit is per person

    async def test_due_open_attempt_is_expired_and_a_new_one_started(self):
        aid = await self.start()
        self.clock.advance(LIMIT_MS)
        session = await self.svc.start_or_resume(ALICE, self.sid)
        self.assertNotEqual(session.attempt.id, aid)
        self.assertTrue(session.created)
        self.assertEqual((await self.repo.get(aid)).status, "expired")

    async def test_unpublished_set_not_found(self):
        draft = await self.seed(publish=False)
        with self.assertRaises(NotFound):
            await self.svc.start_or_resume(ALICE, draft)
        with self.assertRaises(NotFound):
            await self.svc.start_or_resume(ALICE, 9999)


class SaveTest(AttemptCase):
    async def test_save_replaces_selection(self):
        aid = await self.start()
        q = self.q1
        first, second = sorted(q.correct)[:2]
        await self.svc.save(ALICE, aid, q.question_id, [first, second])
        await self.svc.save(ALICE, aid, q.question_id, [second])
        session = await self.svc.session(ALICE, aid)
        self.assertEqual(session.selections, {q.question_id: frozenset({second})})

    async def test_save_rejects_foreign_option_and_question(self):
        aid = await self.start()
        option_of_q2 = next(iter(self.q2.correct))
        with self.assertRaises(Invalid):
            await self.svc.save(ALICE, aid, self.q1.question_id, [option_of_q2])
        other_set = await self.seed()
        [foreign_q, *_] = await self.keys.answer_key(other_set)
        with self.assertRaises(Invalid):
            await self.svc.save(ALICE, aid, foreign_q.question_id, list(foreign_q.correct))
        self.assertEqual((await self.svc.session(ALICE, aid)).selections, {})

    async def test_save_within_grace_ok_after_grace_conflict(self):
        aid = await self.start()
        q = self.q1
        self.clock.advance(LIMIT_MS + 9_000)
        await self.svc.save(ALICE, aid, q.question_id, list(q.correct))  # 9 s past: accepted
        self.assertEqual((await self.repo.get(aid)).status, "in_progress")  # save did not expire it
        self.clock.advance(2_000)
        with self.assertRaises(Conflict) as caught:  # 11 s past: rejected
            await self.svc.save(ALICE, aid, q.question_id, [])
        self.assertEqual(caught.exception.message, "attempt finished")
        self.assertEqual(await self.repo.selections(aid), {q.question_id: q.correct})

    async def test_save_on_finished_attempt_conflict(self):
        aid = await self.start()
        await self.svc.submit(ALICE, aid)
        with self.assertRaises(Conflict):
            await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))

    async def test_empty_option_ids_clears_answer(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.save(ALICE, aid, self.q2.question_id, list(self.q2.correct))
        await self.svc.save(ALICE, aid, self.q1.question_id, [])
        session = await self.svc.session(ALICE, aid)
        self.assertEqual(session.selections, {self.q2.question_id: self.q2.correct})


class SubmitTest(AttemptCase):
    async def test_submit_grades_and_is_idempotent(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.save(ALICE, aid, self.q2.question_id, list(self.q2.correct))
        self.clock.advance(60_000)
        first = await self.svc.submit(ALICE, aid)
        self.assertEqual(first.status, "submitted")
        self.assertEqual(first.finished_at, START + 60_000)
        self.assertEqual(first.score, 3)  # 1 + 2 points; q3 blank
        self.assertEqual(first.max_score, 4)
        self.clock.advance(60_000)
        second = await self.svc.submit(ALICE, aid)
        self.assertEqual(second, first)
        self.assertEqual(await self.count_results(aid), 3)

    async def test_second_finish_does_not_write(self):
        aid = await self.start()
        await self.svc.submit(ALICE, aid)
        attempt = await self.repo.get(aid)
        bogus = GradeResult(99, 99, (QuestionResult(self.q1.question_id, 99, True),))
        self.assertFalse(await self.repo.finish(aid, "submitted", START + 1, bogus))
        self.assertEqual(await self.repo.get(aid), attempt)
        self.assertEqual(await self.count_results(aid), 3)

    async def test_submit_after_deadline_is_expired_at_deadline(self):
        aid = await self.start()
        self.clock.advance(LIMIT_MS + 5_000)
        attempt = await self.svc.submit(ALICE, aid)
        self.assertEqual(attempt.status, "expired")
        self.assertEqual(attempt.finished_at, START + LIMIT_MS)
        self.assertEqual(attempt.score, 0)

    async def test_lazy_expiry_on_read_grades_saved_answers(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        self.clock.advance(16 * 60_000)
        session = await self.svc.session(ALICE, aid)
        self.assertEqual(session.attempt.status, "expired")
        self.assertEqual(session.attempt.score, 1)
        self.assertEqual(session.attempt.finished_at, START + LIMIT_MS)

    async def test_expiry_happens_at_deadline_not_after_grace(self):
        aid = await self.start()
        self.clock.advance(LIMIT_MS)
        self.assertEqual((await self.svc.session(ALICE, aid)).attempt.status, "expired")

    async def test_expire_due_for_user_closes_all_their_due_attempts(self):
        other = await self.seed()
        untimed = await self.seed(time_limit_minutes=None)
        a1 = await self.start()
        a2 = await self.start(set_id=other)
        a3 = await self.start(set_id=untimed)
        bobs = await self.start(BOB)
        self.clock.advance(LIMIT_MS + 1)
        await self.svc.expire_due_for(ALICE)
        self.assertEqual((await self.repo.get(a1)).status, "expired")
        self.assertEqual((await self.repo.get(a2)).status, "expired")
        self.assertEqual((await self.repo.get(a3)).status, "in_progress")
        self.assertEqual((await self.repo.get(bobs)).status, "in_progress")
        self.assertEqual(await self.count_results(a1), 3)


class ResultsTest(AttemptCase):
    async def test_results_conflict_while_open(self):
        aid = await self.start()
        with self.assertRaises(Conflict) as caught:
            await self.svc.results(ALICE, aid)
        self.assertEqual(caught.exception.message, "attempt in progress")

    async def test_results_view(self):
        aid = await self.start()
        wrong = sorted(self.q2.correct)[:1]
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.svc.save(ALICE, aid, self.q2.question_id, wrong)
        await self.svc.submit(ALICE, aid)
        view = await self.svc.results(ALICE, aid)
        self.assertEqual(view.attempt.status, "submitted")
        self.assertEqual(view.set.id, self.sid)
        self.assertEqual([q.id for q in view.questions], [self.q1.question_id, self.q2.question_id, self.q3.question_id])
        self.assertEqual(view.selections[self.q2.question_id], frozenset(wrong))
        self.assertTrue(view.results[self.q1.question_id].is_correct)
        self.assertEqual(view.results[self.q1.question_id].awarded_points, 1)
        self.assertFalse(view.results[self.q2.question_id].is_correct)
        self.assertEqual(view.results[self.q3.question_id].awarded_points, 0)

    async def test_results_lazily_expire(self):
        aid = await self.start()
        self.clock.advance(LIMIT_MS)
        view = await self.svc.results(ALICE, aid)
        self.assertEqual(view.attempt.status, "expired")


class OwnershipAndOrderTest(AttemptCase):
    async def test_foreign_attempt_not_found(self):
        aid = await self.start()
        q = self.q1
        for call in (
            lambda: self.svc.session(BOB, aid),
            lambda: self.svc.save(BOB, aid, q.question_id, list(q.correct)),
            lambda: self.svc.submit(BOB, aid),
            lambda: self.svc.results(BOB, aid),
            lambda: self.svc.session(ALICE, "no-such-attempt"),
        ):
            with self.assertRaises(NotFound):
                await call()
        self.assertEqual((await self.repo.get(aid)).status, "in_progress")
        self.assertEqual(await self.repo.selections(aid), {})

    async def test_display_order_used_when_shuffling(self):
        sid = await self.seed(shuffle_questions=True, shuffle_options=True)
        aids = [await self._start_and_finish(sid) for _ in range(4)]
        solver = await self.catalog.questions_for_solver(sid)
        orders = set()
        for aid in aids:
            expected = display_order(aid, solver, True, True)
            session = await self.svc.session(ALICE, aid)
            self.assertEqual(session.questions, expected)
            view = await self.svc.results(ALICE, aid)
            self.assertEqual(
                [(q.id, [o.id for o in q.options]) for q in view.questions],
                [(q.id, [o.id for o in q.options]) for q in expected],
            )
            orders.add(tuple((q.id, tuple(o.id for o in q.options)) for q in expected))
        self.assertGreater(len(orders), 1)  # the shuffle actually varies by attempt

    async def _start_and_finish(self, sid) -> str:
        aid = await self.start(set_id=sid)
        await self.svc.submit(ALICE, aid)
        return aid


class HistoryTest(AttemptCase):
    async def test_history_newest_first_and_expires_first(self):
        other = await self.seed()
        a1 = await self.start()
        self.clock.advance(1_000)
        a2 = await self.start(set_id=other)
        await self.start(BOB)
        self.clock.advance(LIMIT_MS)
        history = await self.svc.history(ALICE)
        self.assertEqual([a.id for a, _ in history], [a2, a1])
        self.assertEqual([s.id for _, s in history], [other, self.sid])
        self.assertEqual({a.status for a, _ in history}, {"expired"})

    async def test_repository_user_queries(self):
        other = await self.seed()
        a1 = await self.start()
        await self.svc.submit(ALICE, a1)
        self.clock.advance(1_000)
        a2 = await self.start()
        await self.svc.submit(ALICE, a2)
        a3 = await self.start()
        a4 = await self.start(set_id=other)
        self.assertEqual(await self.repo.count_finished(self.sid, ALICE), 2)
        self.assertEqual({a.id for a in await self.repo.open_for_user(ALICE)}, {a3, a4})
        last = await self.repo.last_finished_by_set(ALICE)
        self.assertEqual({k: v.id for k, v in last.items()}, {self.sid: a2})
        self.assertEqual((await self.repo.open_for(other, ALICE)).id, a4)
        self.assertIsNone(await self.repo.open_for(other, BOB))



class ArchivedSetTest(AttemptCase):
    async def archive(self):
        await self.authoring.archive(ADMIN, self.sid)

    async def test_open_attempt_survives_archiving(self):
        aid = await self.start()
        await self.archive()
        session = await self.svc.session(ALICE, aid)
        self.assertEqual(session.attempt.status, "in_progress")
        self.assertEqual(len(session.questions), 3)
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        attempt = await self.svc.submit(ALICE, aid)
        self.assertEqual((attempt.status, attempt.score), ("submitted", 1))
        view = await self.svc.results(ALICE, aid)
        self.assertEqual(view.set.status, "archived")
        self.assertEqual(len(view.questions), 3)
        self.assertTrue(view.results[self.q1.question_id].is_correct)

    async def test_due_attempt_on_archived_set_is_expired_and_graded(self):
        aid = await self.start()
        await self.svc.save(ALICE, aid, self.q1.question_id, list(self.q1.correct))
        await self.archive()
        self.clock.advance(LIMIT_MS + 1)
        await self.svc.expire_due_for(ALICE)
        attempt = await self.repo.get(aid)
        self.assertEqual((attempt.status, attempt.score, attempt.finished_at), ("expired", 1, START + LIMIT_MS))
        self.assertEqual(await self.count_results(aid), 3)

    async def test_history_lists_attempts_on_archived_set(self):
        aid = await self.start()
        await self.svc.submit(ALICE, aid)
        await self.archive()
        history = await self.svc.history(ALICE)
        self.assertEqual([(a.id, s.id) for a, s in history], [(aid, self.sid)])

    async def test_cannot_start_on_archived_set(self):
        await self.archive()
        with self.assertRaises(NotFound):
            await self.svc.start_or_resume(ALICE, self.sid)


if __name__ == "__main__":
    unittest.main()
