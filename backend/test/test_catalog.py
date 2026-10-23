"""Catalog (solver view) and answer key reader over a seeded SQLite D1.

Run:  python3 test/test_catalog.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "test"))

from helpers import fresh_db, sample_import  # noqa: E402

from quiz_app.clock import FakeClock  # noqa: E402
from quiz_app.d1.authoring import D1QuizAuthoring  # noqa: E402
from quiz_app.d1.catalog import D1AnswerKey, D1Catalog  # noqa: E402
from quiz_app.d1.users import D1UserRepository  # noqa: E402
from quiz_app.models import User  # noqa: E402
from quiz_app.services.authoring import AuthoringService  # noqa: E402

ADMIN = User("admin@example.com", "Admin", "admin")
START = 1_700_000_000_000


class CatalogCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = fresh_db()
        clock = FakeClock(START)
        await D1UserRepository(self.db, clock).get_or_create(ADMIN.email)
        self.authoring = AuthoringService(D1QuizAuthoring(self.db, clock), clock)
        self.catalog = D1Catalog(self.db)
        self.key = D1AnswerKey(self.db)

    async def seed(self, status="published", **overrides) -> int:
        info = await self.authoring.import_set(ADMIN, sample_import(**overrides))
        if status == "published":
            await self.authoring.publish(ADMIN, info.id)
        elif status == "archived":
            await self.authoring.archive(ADMIN, info.id)
        return info.id


class ListPublishedTest(CatalogCase):
    async def test_list_published_excludes_draft_and_archived(self):
        published = await self.seed("published")
        await self.seed("draft")
        await self.seed("archived")
        listed = await self.catalog.list_published()
        self.assertEqual([s.id for s in listed], [published])

    async def test_question_count_and_names(self):
        set_id = await self.seed(difficulty="hard")
        [info] = await self.catalog.list_published()
        self.assertEqual(info.id, set_id)
        self.assertEqual(info.question_count, 3)
        self.assertEqual(info.topic_name, "RAG")
        self.assertEqual(info.subtopic_name, "Embeddings and vector space")
        self.assertEqual(info.name, "Embeddings and vector space · Hard · Set 1")
        self.assertEqual(info.short_name, "Hard · Set 1")

    async def test_list_orders_by_topic_subtopic_then_seq(self):
        first = await self.seed()
        second = await self.seed()
        other = await self.seed(subtopic={"slug": "chunking", "name": "Chunking"})
        listed = await self.catalog.list_published()
        self.assertEqual([s.id for s in listed], [first, second, other])
        self.assertEqual([s.seq for s in listed], [1, 2, 1])

    async def test_get_set_is_published_only(self):
        published = await self.seed("published")
        draft = await self.seed("draft")
        archived = await self.seed("archived")
        self.assertEqual((await self.catalog.get_set(published)).id, published)
        self.assertIsNone(await self.catalog.get_set(draft))
        self.assertIsNone(await self.catalog.get_set(archived))
        self.assertIsNone(await self.catalog.get_set(9999))


class SolverQuestionsTest(CatalogCase):
    async def test_solver_questions_in_authored_order_without_answers(self):
        set_id = await self.seed()
        qs = await self.catalog.questions_for_solver(set_id)
        self.assertEqual(
            [q.prompt for q in qs], [q["prompt"] for q in sample_import()["questions"]]
        )
        self.assertEqual(
            [o.body for o in qs[0].options],
            [
                "Every stored vector must be re-embedded",
                "The vector dimension may change",
                "The chunking boundaries",
                "Similarity thresholds need re-tuning",
            ],
        )
        dumped = json.dumps([dataclasses.asdict(q) for q in qs])
        for leaked in ("is_correct", "correct", "explanation"):
            self.assertNotIn(leaked, dumped)

    async def test_unknown_set_has_no_questions(self):
        self.assertEqual(await self.catalog.questions_for_solver(9999), [])


class AnswerKeyTest(CatalogCase):
    async def test_answer_key_matches_import(self):
        set_id = await self.seed()
        keys = await self.key.answer_key(set_id)
        self.assertEqual([k.points for k in keys], [1, 2, 1])
        qs = await self.catalog.questions_for_solver(set_id)
        imported = sample_import()["questions"]
        for key, solver_q, source in zip(keys, qs, imported):
            self.assertEqual(key.question_id, solver_q.id)
            expected = {o.id for o, src in zip(solver_q.options, source["options"]) if src["correct"]}
            self.assertEqual(key.correct, frozenset(expected))

    async def test_answer_key_works_for_a_draft(self):
        set_id = await self.seed("draft")
        keys = await self.key.answer_key(set_id)
        self.assertEqual([len(k.correct) for k in keys], [3, 2, 1])

    async def test_review_questions_carry_explanations(self):
        set_id = await self.seed("archived")
        review = await self.key.review_questions(set_id)
        self.assertEqual(
            [r.explanation for r in review],
            ["Vectors from different models are not comparable.",
             "Cosine and dot product are the usual choices.", None],
        )
        self.assertEqual([r.points for r in review], [1, 2, 1])
        self.assertEqual(
            [(o.body, o.is_correct) for o in review[1].options],
            [("Cosine similarity", True), ("Dot product", True), ("Levenshtein distance", False)],
        )

    async def test_unknown_set_has_empty_key(self):
        self.assertEqual(await self.key.answer_key(9999), [])
        self.assertEqual(await self.key.review_questions(9999), [])


if __name__ == "__main__":
    unittest.main()
