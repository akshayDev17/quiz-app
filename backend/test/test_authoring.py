"""Authoring and users: D1 repositories over SqliteD1, validation, services.

Run:  python3 test/test_authoring.py
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from dataclasses import replace
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "test"))

from helpers import fresh_db, sample_import  # noqa: E402

from quiz_app.auth import Identity  # noqa: E402
from quiz_app.clock import FakeClock  # noqa: E402
from quiz_app.d1.authoring import D1QuizAuthoring  # noqa: E402
from quiz_app.d1.users import D1UserRepository  # noqa: E402
from quiz_app.errors import Forbidden, Invalid, NotFound  # noqa: E402
from quiz_app.models import User  # noqa: E402
from quiz_app.services.authoring import AuthoringService  # noqa: E402
from quiz_app.services.users import UserService  # noqa: E402
from quiz_app.validation import QuizValidator  # noqa: E402

ADMIN = User("admin@example.com", "Admin", "admin")
SOLVER = User("solver@example.com", "Sol", "solver")
START = 1_700_000_000_000

BASE = sample_import()


def q(**overrides) -> dict:
    """BASE with its first question replaced; ``options`` takes (body, correct) pairs."""
    question = {"prompt": "A prompt", "options": [("a", True), ("b", False)]}
    question.update(overrides)
    question["options"] = [{"body": b, "correct": c} for b, c in question["options"]]
    return dict(BASE, questions=[question])


class AuthoringCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = fresh_db()
        self.clock = FakeClock(START)
        self.users = D1UserRepository(self.db, self.clock)
        self.repo = D1QuizAuthoring(self.db, self.clock)
        self.service = AuthoringService(self.repo, self.clock)
        await self.users.get_or_create(ADMIN.email)

    async def rows(self, sql, *params):
        return (await self.db.prepare(sql).bind(*params).all()).results


class ImportTest(AuthoringCase):
    async def test_import_creates_topic_subtopic_and_seq_1(self):
        info = await self.service.import_set(ADMIN, sample_import())
        self.assertEqual(info.name, "Embeddings and vector space · Set 1")
        self.assertEqual(info.status, "draft")
        self.assertEqual((info.topic_name, info.subtopic_name, info.seq), ("RAG", "Embeddings and vector space", 1))
        self.assertEqual(info.question_count, 3)
        self.assertEqual(info.time_limit_minutes, 15)

    async def test_import_stores_questions_options_and_correctness(self):
        info = await self.service.import_set(ADMIN, sample_import())
        questions = await self.rows("SELECT * FROM questions WHERE set_id = ? ORDER BY position", info.id)
        self.assertEqual([r["position"] for r in questions], [0, 1, 2])
        self.assertEqual([r["points"] for r in questions], [1, 2, 1])
        self.assertIsNone(questions[2]["explanation"])
        options = await self.rows(
            "SELECT body, is_correct FROM options WHERE question_id = ? ORDER BY position", questions[0]["id"]
        )
        self.assertEqual([r["is_correct"] for r in options], [1, 1, 0, 1])
        self.assertEqual(options[2]["body"], "The chunking boundaries")

    async def test_second_import_same_bucket_gets_seq_2(self):
        await self.service.import_set(ADMIN, sample_import())
        second = await self.service.import_set(ADMIN, sample_import())
        self.assertEqual(second.seq, 2)
        self.assertEqual(second.name, "Embeddings and vector space · Set 2")

    async def test_different_difficulty_is_a_different_bucket(self):
        easy = await self.service.import_set(ADMIN, sample_import(difficulty="easy"))
        medium = await self.service.import_set(ADMIN, sample_import(difficulty="medium"))
        self.assertEqual((easy.seq, medium.seq), (1, 1))
        self.assertEqual(easy.name, "Embeddings and vector space · Easy · Set 1")
        self.assertEqual(medium.name, "Embeddings and vector space · Medium · Set 1")

    async def test_whole_topic_set_has_its_own_bucket(self):
        await self.service.import_set(ADMIN, sample_import())
        whole = await self.service.import_set(ADMIN, sample_import(subtopic=None))
        self.assertEqual(whole.seq, 1)
        self.assertIsNone(whole.subtopic_id)
        self.assertEqual(whole.name, "Set 1")

    async def test_existing_topic_found_by_slug_name_not_overwritten(self):
        first = await self.service.import_set(ADMIN, sample_import())
        other = sample_import(
            topic={"slug": "rag", "name": "Retrieval (renamed)"},
            subtopic={"slug": "embeddings", "name": "Other name"},
        )
        second = await self.service.import_set(ADMIN, other)
        self.assertEqual((second.topic_id, second.subtopic_id), (first.topic_id, first.subtopic_id))
        self.assertEqual(second.topic_name, "RAG")
        self.assertEqual(second.subtopic_name, "Embeddings and vector space")
        self.assertEqual((await self.rows("SELECT COUNT(*) AS n FROM topics"))[0]["n"], 1)
        self.assertEqual((await self.rows("SELECT COUNT(*) AS n FROM subtopics"))[0]["n"], 1)

    async def test_blank_title_description_and_explanation_become_none(self):
        payload = sample_import(title="   ", description="")
        payload["questions"][0]["explanation"] = "  "
        imp = QuizValidator.parse(payload)
        self.assertIsNone(imp.title)
        self.assertIsNone(imp.description)
        self.assertIsNone(imp.questions[0].explanation)
        info = await self.service.import_set(ADMIN, payload)
        self.assertIsNone(info.title)
        self.assertEqual(info.name, "Embeddings and vector space · Set 1")

    async def test_rules_and_flags_are_stored(self):
        info = await self.service.import_set(ADMIN, sample_import(
            scoring_policy="partial", shuffle_questions=True, reveal_answers=False,
            max_attempts=3, time_limit_minutes=None, title="Custom", description="About",
        ))
        self.assertEqual(
            (info.scoring_policy, info.shuffle_questions, info.shuffle_options, info.reveal_answers),
            ("partial", True, False, False),
        )
        self.assertEqual((info.max_attempts, info.time_limit_minutes), (3, None))
        self.assertEqual((info.title, info.description, info.name), ("Custom", "About", "Custom"))

    async def test_failed_option_insert_leaves_no_half_built_set(self):
        payload = sample_import()
        # Bypass the validator: a second correct flag of 2 violates the CHECK mid-import.
        imp = QuizValidator.parse(payload)
        bad = imp.questions[1].options + (("x", 2),)
        imp = replace(imp, questions=(imp.questions[0], replace(imp.questions[1], options=bad)))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.create_set(imp, ADMIN.email, START)
        self.assertEqual((await self.rows("SELECT COUNT(*) AS n FROM quiz_sets"))[0]["n"], 0)
        self.assertEqual((await self.rows("SELECT COUNT(*) AS n FROM questions"))[0]["n"], 0)


class ValidatorTest(unittest.TestCase):
    def test_validator_rejects(self):
        for bad, fragment in [
            (q(options=[("only", True)]), "at least 2 options"),
            (q(options=[("a", False), ("b", False)]), "at least 1 correct"),
            (q(prompt="  "), "empty prompt"),
            (dict(BASE, difficulty="insane"), "difficulty"),
            (dict(BASE, scoring_policy="negative"), "scoring_policy"),
            (dict(BASE, time_limit_minutes=0), "time_limit_minutes"),
            (dict(BASE, questions=[]), "at least 1 question"),
            (dict(BASE, topic={"slug": "Bad Slug", "name": "x"}), "slug"),
        ]:
            with self.subTest(fragment=fragment):
                with self.assertRaises(Invalid) as ctx:
                    QuizValidator.parse(bad)
                self.assertIn(fragment, str(ctx.exception.message))

    def test_all_messages_are_joined(self):
        with self.assertRaises(Invalid) as ctx:
            QuizValidator.parse(dict(BASE, difficulty="insane", scoring_policy="negative"))
        message = ctx.exception.message
        self.assertIn("difficulty", message)
        self.assertIn("scoring_policy", message)
        self.assertIn("; ", message)

    def test_defaults(self):
        imp = QuizValidator.parse({
            "topic": {"slug": "rag", "name": "RAG"},
            "questions": [{"prompt": "p", "options": [{"body": "a", "correct": True}, {"body": "b", "correct": False}]}],
        })
        self.assertEqual((imp.style, imp.scoring_policy), ("standard", "all_or_nothing"))
        self.assertEqual((imp.shuffle_questions, imp.shuffle_options, imp.reveal_answers), (False, False, True))
        self.assertEqual((imp.subtopic, imp.difficulty, imp.time_limit_minutes, imp.max_attempts), (None, None, None, None))
        self.assertEqual(imp.questions[0].points, 1)
        self.assertEqual(imp.questions[0].options, (("a", True), ("b", False)))

    def test_rejects_bad_types(self):
        for bad in [
            dict(BASE, time_limit_minutes=True),
            dict(BASE, time_limit_minutes=1.5),
            dict(BASE, max_attempts=0),
            dict(BASE, shuffle_options="yes"),
            dict(BASE, style="quiz"),
            q(points=0),
            q(options=[("a", True), ("", False)]),
        ]:
            with self.subTest(bad=str(bad)[:60]):
                with self.assertRaises(Invalid):
                    QuizValidator.parse(bad)
        with self.assertRaises(Invalid):
            QuizValidator.parse([])


class PublishArchiveCloneTest(AuthoringCase):
    async def test_publish_and_archive_change_status(self):
        info = await self.service.import_set(ADMIN, sample_import())
        self.clock.advance(5000)
        self.assertEqual((await self.service.publish(ADMIN, info.id)).status, "published")
        self.assertEqual((await self.service.archive(ADMIN, info.id)).status, "archived")
        row = (await self.rows("SELECT updated_at FROM quiz_sets WHERE id = ?", info.id))[0]
        self.assertEqual(row["updated_at"], START + 5000)

    async def test_get_returns_drafts_and_none_for_missing(self):
        info = await self.service.import_set(ADMIN, sample_import())
        fetched = await self.repo.get(info.id)
        self.assertEqual((fetched.status, fetched.question_count), ("draft", 3))
        self.assertEqual(fetched, info)
        self.assertIsNone(await self.repo.get(999))

    async def test_missing_set_is_not_found(self):
        for call in (self.service.publish, self.service.archive, self.service.clone):
            with self.subTest(call=call.__name__):
                with self.assertRaises(NotFound):
                    await call(ADMIN, 999)

    async def test_clone_copies_questions_into_next_seq_draft(self):
        original = await self.service.import_set(ADMIN, sample_import(
            scoring_policy="partial", shuffle_options=True, max_attempts=2, description="About", title=None,
        ))
        await self.service.publish(ADMIN, original.id)
        copy = await self.service.clone(ADMIN, original.id)

        self.assertNotEqual(copy.id, original.id)
        self.assertEqual((copy.status, copy.seq), ("draft", 2))
        self.assertEqual(copy.name, "Embeddings and vector space · Set 2")
        self.assertEqual(
            (copy.scoring_policy, copy.shuffle_options, copy.max_attempts, copy.description, copy.time_limit_minutes),
            ("partial", True, 2, "About", 15),
        )
        self.assertEqual(copy.question_count, 3)

        def shape(set_id):
            return self.rows(
                "SELECT q.position, q.prompt, q.explanation, q.points, o.position AS opos, o.body, o.is_correct "
                "FROM questions q JOIN options o ON o.question_id = q.id WHERE q.set_id = ? "
                "ORDER BY q.position, o.position", set_id)

        self.assertEqual(await shape(copy.id), await shape(original.id))
        ids = lambda set_id: self.rows("SELECT id FROM questions WHERE set_id = ?", set_id)  # noqa: E731
        self.assertFalse({r["id"] for r in await ids(copy.id)} & {r["id"] for r in await ids(original.id)})
        # The original is untouched.
        self.assertEqual((await self.repo.get(original.id)).status, "published")

    async def test_clone_attributes_to_the_cloner(self):
        original = await self.service.import_set(ADMIN, sample_import())
        other_admin = User("other@example.com", None, "admin")
        await self.users.get_or_create(other_admin.email)
        copy = await self.service.clone(other_admin, original.id)
        row = (await self.rows("SELECT created_by FROM quiz_sets WHERE id = ?", copy.id))[0]
        self.assertEqual(row["created_by"], other_admin.email)

    async def test_list_all_includes_every_status_with_attempt_counts(self):
        a = await self.service.import_set(ADMIN, sample_import())
        b = await self.service.import_set(ADMIN, sample_import())
        await self.service.publish(ADMIN, b.id)
        await self.users.get_or_create(SOLVER.email)
        await self.db.prepare(
            "INSERT INTO attempts (id, set_id, user_email, started_at) VALUES ('att-1', ?, ?, ?)"
        ).bind(b.id, SOLVER.email, START).run()

        listing = await self.service.list_all(ADMIN)
        self.assertEqual([(info.id, info.status, count) for info, count in listing],
                         [(b.id, "published", 1), (a.id, "draft", 0)])


class PermissionTest(AuthoringCase):
    async def test_solver_cannot_author(self):
        info = await self.service.import_set(ADMIN, sample_import())
        for call in (
            lambda: self.service.import_set(SOLVER, sample_import()),
            lambda: self.service.publish(SOLVER, info.id),
            lambda: self.service.archive(SOLVER, info.id),
            lambda: self.service.clone(SOLVER, info.id),
            lambda: self.service.list_all(SOLVER),
        ):
            with self.assertRaises(Forbidden):
                await call()
        self.assertEqual((await self.repo.get(info.id)).status, "draft")


class UserServiceTest(AuthoringCase):
    def service_for(self, admins=("admin@example.com",)):
        return UserService(self.users, frozenset(admins))

    async def test_display_name_rules(self):
        users = self.service_for()
        who = Identity("solver@example.com")
        self.assertIsNone((await users.me(who)).display_name)
        self.assertEqual((await users.rename(who, "  Akshay  ")).display_name, "Akshay")
        self.assertEqual((await users.me(who)).display_name, "Akshay")
        for bad in ("", "   ", "x" * 61):
            with self.subTest(length=len(bad)):
                with self.assertRaises(Invalid):
                    await users.rename(who, bad)
        self.assertEqual((await users.rename(who, "x" * 60)).display_name, "x" * 60)
        self.assertEqual((await users.me(who)).display_name, "x" * 60)

    async def test_admin_role_comes_from_admin_emails(self):
        users = self.service_for(admins=("Boss@Example.com", "other@example.com"))
        self.assertEqual((await users.me(Identity("BOSS@example.com"))).role, "admin")
        self.assertEqual((await users.me(Identity("someone@example.com"))).role, "solver")
        self.assertEqual((await users.rename(Identity("boss@example.com"), "Boss")).role, "admin")

    async def test_stored_role_is_overridden_both_ways(self):
        await self.db.prepare("UPDATE users SET role = 'admin' WHERE email = ?").bind(ADMIN.email).run()
        self.assertEqual((await self.service_for(admins=()).me(Identity(ADMIN.email))).role, "solver")

    async def test_get_or_create_is_idempotent(self):
        await self.users.get_or_create("new@example.com")
        again = await self.users.get_or_create("new@example.com")
        self.assertEqual(again, User("new@example.com", None, "solver"))
        self.assertEqual((await self.rows("SELECT COUNT(*) AS n FROM users WHERE email = 'new@example.com'"))[0]["n"], 1)


class SqliteD1Test(AuthoringCase):
    async def test_batch_is_atomic(self):
        insert = "INSERT INTO topics (slug, name, created_at) VALUES (?, ?, 0)"
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.batch([
                self.db.prepare(insert).bind("a", "A"),
                self.db.prepare(insert).bind("b", "B"),
                self.db.prepare(insert).bind("a", "dup"),
            ])
        self.assertEqual(await self.rows("SELECT * FROM topics"), [])
        # The binding is still usable after a rollback, and a good batch commits.
        await self.db.batch([self.db.prepare(insert).bind("a", "A"), self.db.prepare(insert).bind("b", "B")])
        self.assertEqual(len(await self.rows("SELECT * FROM topics")), 2)

    async def test_run_outside_a_batch_autocommits(self):
        await self.db.prepare("INSERT INTO topics (slug, name, created_at) VALUES ('a', 'A', 0)").run()
        self.assertFalse(self.db._conn.in_transaction)

    async def test_foreign_keys_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.prepare(
                "INSERT INTO subtopics (topic_id, slug, name, created_at) VALUES (99, 's', 'S', 0)"
            ).run()

    async def test_first_and_all_shapes(self):
        self.assertIsNone(await self.db.prepare("SELECT * FROM topics").first())
        self.assertEqual((await self.db.prepare("SELECT * FROM topics").all()).results, [])
        row = await self.db.prepare("SELECT ? AS x").bind(5).first()
        self.assertEqual(row, {"x": 5})


if __name__ == "__main__":
    unittest.main()
