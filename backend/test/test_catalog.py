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
from quiz_app.d1.catalog import D1Catalog, D1PaperSource  # noqa: E402
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
        self.papers = D1PaperSource(self.db)

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

class PaperSourceTest(CatalogCase):
    """The set-scoped read: what a new attempt copies. Read once, at start."""

    async def test_source_is_authored_order_with_the_answer_key(self):
        set_id = await self.seed()
        source = await self.papers.paper_source(set_id)
        imported = sample_import()["questions"]
        self.assertEqual([q.prompt for q in source], [q["prompt"] for q in imported])
        self.assertEqual([q.points for q in source], [1, 2, 1])
        self.assertEqual(
            [r.explanation for r in source],
            ["Vectors from different models are not comparable.",
             "Cosine and dot product are the usual choices.", None],
        )
        self.assertEqual(
            [(o.body, o.is_correct) for o in source[1].options],
            [("Cosine similarity", True), ("Dot product", True), ("Levenshtein distance", False)],
        )

    async def test_source_is_available_for_an_archived_set(self):
        # Not a solver read: an attempt starting is the only caller, and it is told
        # separately whether the set is published.
        set_id = await self.seed("archived")
        self.assertEqual(len(await self.papers.paper_source(set_id)), 3)

    async def test_unknown_set_has_no_paper(self):
        self.assertEqual(await self.papers.paper_source(9999), [])


if __name__ == "__main__":
    unittest.main()
