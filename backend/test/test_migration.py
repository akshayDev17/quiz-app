"""Migrations over a live database's data: 0003 backfills papers, 0004 adds visibility,
0005 adds subjective.

0003 is the one migration that touches data it did not create, so it gets its own
test: build a pre-0003 database by hand, seed it the way the old schema would have,
apply 0003 (and everything after it), and check both that nothing was lost and that
the result is usable through the repositories. 0004 and 0005 only add; their tests
check that the same seeded rows come through untouched (every set public, every
question a choice question with its score intact) and that their new constraints hold.
"""

from __future__ import annotations

import re
import sqlite3
import unittest

import helpers  # noqa: F401  (sys.path)

from helpers import MIGRATIONS

from quiz_app.d1.attempts import D1AttemptRepository
from quiz_app.d1.sqlite_binding import SqliteD1

SEED = """
INSERT INTO users (email, display_name, role, created_at) VALUES ('a@x.com', 'A', 'admin', 1);
INSERT INTO topics (id, slug, name, position, created_at)
  VALUES (1, 'harness-engineering', 'Harness Engineering', 0, 1);
INSERT INTO subtopics (id, topic_id, slug, name, position, created_at)
  VALUES (1, 1, 'model-failure-science', 'Model Failure Science', 0, 1);
INSERT INTO quiz_sets (id, topic_id, subtopic_id, difficulty, style, seq, title, description,
  time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers,
  max_attempts, status, created_by, created_at, updated_at)
VALUES (3, 1, 1, 'hard', 'standard', 1, NULL, 'Consensus fundamentals.', 20, 'partial', 0, 0, 1,
  3, 'published', 'a@x.com', 1, 1);
INSERT INTO questions (id, set_id, position, prompt, explanation, points) VALUES
  (10, 3, 0, 'What does the leader do?', 'Replicates the log.', 2),
  (11, 3, 1, 'Quorum for 5 nodes?', NULL, 1);
INSERT INTO options (id, question_id, position, body, is_correct) VALUES
  (100, 10, 0, 'Appends then replicates', 1), (101, 10, 1, 'Deletes the log', 0),
  (102, 11, 0, '3 nodes', 1), (103, 11, 1, '2 nodes', 0);

-- one finished attempt, with answers and a grade
INSERT INTO attempts (id, set_id, user_email, started_at, deadline_at, finished_at, status, score, max_score)
  VALUES ('finished', 3, 'a@x.com', 1000, 2000, 1500, 'submitted', 2.0, 3.0);
INSERT INTO attempt_selections (attempt_id, question_id, option_id) VALUES
  ('finished', 10, 100), ('finished', 11, 102);
INSERT INTO attempt_results (attempt_id, question_id, awarded_points, is_correct) VALUES
  ('finished', 10, 2.0, 1), ('finished', 11, 0.0, 0);

-- one paused, still-open attempt
INSERT INTO attempts (id, set_id, user_email, started_at, deadline_at, status, paused_at)
  VALUES ('paused', 3, 'a@x.com', 3000, 4000, 'in_progress', 3500);
INSERT INTO attempt_selections (attempt_id, question_id, option_id) VALUES ('paused', 10, 101);
"""


def _migrated_from(seed_before: str, seed: str) -> SqliteD1:
    """Every migration before ``seed_before`` (a file name), then ``seed``, then the rest.

    The repositories read the schema as it is at head, so a test of one migration's
    backfill applies every later migration too before using them."""
    db = SqliteD1(":memory:")
    paths = sorted(MIGRATIONS.glob("*.sql"))
    for path in paths:
        if path.name == seed_before:
            db.executescript(seed)
        db.executescript(path.read_text())
    return db


def _pre_migration_db() -> SqliteD1:
    return _migrated_from("0003_attempt_papers.sql", SEED)


class MigrationFileTest(unittest.TestCase):
    """The rules every migration file has to obey to run on D1 at all.

    Learned the hard way: an explicit BEGIN in 0003 failed the deploy with
    "To execute a transaction, please use state.storage.transaction() …" (code
    7500). `PRAGMA foreign_keys = OFF` is not a way out either — D1 always
    enforces foreign keys, so a rebuild has to be ordered instead.
    """

    def statements(self, path) -> str:
        """The file with comment-only lines stripped."""
        return "\n".join(
            line for line in path.read_text().splitlines()
            if not line.lstrip().startswith("--")
        )

    def test_no_explicit_transactions(self):
        for path in sorted(MIGRATIONS.glob("*.sql")):
            body = self.statements(path)
            for keyword in ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT"):
                found = re.search(rf"^\s*{keyword}\b", body, re.IGNORECASE | re.MULTILINE)
                self.assertIsNone(
                    found, f"{path.name}: D1 rejects explicit {keyword}; order the statements instead"
                )

    def test_foreign_keys_are_never_disabled(self):
        # Enabling it (0001 does) is harmless; disabling it is impossible on D1.
        for path in sorted(MIGRATIONS.glob("*.sql")):
            found = re.search(
                r"PRAGMA\s+foreign_keys\s*=\s*(OFF|0)\b",
                self.statements(path), re.IGNORECASE,
            )
            self.assertIsNone(found, f"{path.name}: D1 cannot disable foreign keys")


class MigrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = _pre_migration_db()
        self.repo = D1AttemptRepository(self.db)

    async def rows(self, sql, *params):
        return [dict(r) for r in (await self.db.prepare(sql).bind(*params).all()).results]

    async def test_no_foreign_key_violations_after_the_rebuild(self):
        self.assertEqual(await self.rows("PRAGMA foreign_key_check"), [])

    async def test_the_set_label_is_frozen_onto_every_attempt(self):
        for row in await self.rows(
            "SELECT topic_name, subtopic_name, difficulty, style, seq, title, "
            "scoring_policy, reveal_answers FROM attempts"
        ):
            self.assertEqual(
                row,
                {"topic_name": "Harness Engineering", "subtopic_name": "Model Failure Science",
                 "difficulty": "hard", "style": "standard", "seq": 1, "title": None,
                 "scoring_policy": "partial", "reveal_answers": 1},
            )

    async def test_every_attempt_gets_its_paper(self):
        counts = await self.rows(
            "SELECT attempt_id, COUNT(*) AS n FROM attempt_questions GROUP BY attempt_id "
            "ORDER BY attempt_id"
        )
        self.assertEqual({(r["attempt_id"], r["n"]) for r in counts}, {("finished", 2), ("paused", 2)})
        options = await self.rows(
            "SELECT COUNT(*) AS n FROM attempt_options ao "
            "JOIN attempt_questions aq ON aq.id = ao.attempt_question_id"
        )
        self.assertEqual(options[0]["n"], 8)  # 2 attempts x (2 questions x 2 options)

    async def test_papers_carry_the_source_ids_and_the_served_order(self):
        paper = await self.rows(
            "SELECT position, source_question_id, prompt, points FROM attempt_questions "
            "WHERE attempt_id = 'finished' ORDER BY position"
        )
        self.assertEqual([(r["position"], r["source_question_id"]) for r in paper], [(0, 10), (1, 11)])
        self.assertEqual([r["prompt"] for r in paper], ["What does the leader do?", "Quorum for 5 nodes?"])
        self.assertEqual([r["points"] for r in paper], [2.0, 1.0])

        options = await self.rows(
            "SELECT source_option_id, body, is_correct FROM attempt_options "
            "WHERE attempt_question_id = (SELECT id FROM attempt_questions "
            "WHERE attempt_id = 'finished' AND position = 0) ORDER BY position"
        )
        self.assertEqual([(o["source_option_id"], o["is_correct"]) for o in options], [(100, 1), (101, 0)])

    async def test_ticked_options_and_grades_are_rewired_onto_the_paper(self):
        selections = await self.repo.selections("finished")
        self.assertEqual([len(ids) for ids in selections.values()], [1, 1])
        self.assertEqual(len(selections), 2)

        graded = await self.repo.results("finished")
        self.assertEqual(sorted(graded.values(), key=lambda r: r.question_id)[0].awarded_points, 2.0)
        self.assertEqual(len(graded), 2)

        # The paper the app reads back is the one the solver was served.
        paper = await self.repo.paper("finished")
        self.assertEqual([q.prompt for q in paper], ["What does the leader do?", "Quorum for 5 nodes?"])
        self.assertEqual({q.id for q in paper}, set(selections))
        self.assertEqual({q.id for q in paper}, set(graded))

        key = await self.repo.answer_key("finished")
        self.assertEqual([len(k.correct) for k in key], [1, 1])

    async def test_the_paused_attempt_keeps_its_clock(self):
        attempt = await self.repo.get("paused")
        self.assertEqual((attempt.status, attempt.paused_at, attempt.deadline_at),
                         ("in_progress", 3500, 4000))

    async def test_deleting_the_set_now_leaves_every_attempt_intact(self):
        await self.db.prepare("DELETE FROM quiz_sets WHERE id = 3").run()

        self.assertEqual(await self.rows("PRAGMA foreign_key_check"), [])
        finished = await self.repo.get("finished")
        self.assertIsNone(finished.set_id)
        self.assertEqual(finished.name, "Model Failure Science · Hard · Set 1")
        self.assertEqual((finished.score, finished.max_score), (2.0, 3.0))
        self.assertEqual(len(await self.repo.paper("finished")), 2)
        self.assertEqual(len(await self.repo.review("finished")), 2)
        self.assertEqual(len(await self.repo.selections("finished")), 2)


class VisibilityMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0004 adds quiz_sets.visibility. Every set that exists already becomes public, so
    nobody signed in sees anything different the day it deploys."""

    async def asyncSetUp(self):
        self.db = _pre_migration_db()  # seeded before 0003, then every migration

    async def rows(self, sql, *params):
        return [dict(r) for r in (await self.db.prepare(sql).bind(*params).all()).results]

    async def test_existing_sets_become_public(self):
        self.assertEqual(await self.rows("SELECT id, visibility FROM quiz_sets"), [{"id": 3, "visibility": "public"}])

    async def test_new_rows_default_to_public(self):
        await self.db.prepare(
            "INSERT INTO quiz_sets (id, topic_id, style, seq, scoring_policy, status, created_by, "
            "created_at, updated_at) VALUES (4, 1, 'standard', 2, 'partial', 'draft', 'a@x.com', 1, 1)"
        ).run()
        self.assertEqual((await self.rows("SELECT visibility FROM quiz_sets WHERE id = 4"))[0]["visibility"], "public")

    async def test_only_public_and_private_are_allowed(self):
        await self.db.prepare("UPDATE quiz_sets SET visibility = 'private' WHERE id = 3").run()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.prepare("UPDATE quiz_sets SET visibility = 'hidden' WHERE id = 3").run()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db.prepare("UPDATE quiz_sets SET visibility = NULL WHERE id = 3").run()

    async def test_attempts_are_untouched(self):
        attempts = await self.rows("SELECT id, status, score FROM attempts ORDER BY id")
        self.assertEqual(
            attempts,
            [{"id": "finished", "status": "submitted", "score": 2.0},
             {"id": "paused", "status": "in_progress", "score": None}],
        )
        self.assertEqual(await self.rows("PRAGMA foreign_key_check"), [])


class SubjectiveMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0005 adds the subjective kind, the model answer and the typed-answer table."""

    async def asyncSetUp(self):
        self.db = _pre_migration_db()

    async def rows(self, sql, *params):
        return [dict(r) for r in (await self.db.prepare(sql).bind(*params).all()).results]

    async def insert_fails(self, sql, *params):
        with self.assertRaises(Exception) as caught:
            await self.db.prepare(sql).bind(*params).run()
        self.assertIn("constraint failed", str(caught.exception))

    async def test_existing_questions_and_papers_become_choice_questions(self):
        for table in ("questions", "attempt_questions"):
            self.assertEqual(
                {(r["kind"], r["model_answer"]) for r in await self.rows(f"SELECT kind, model_answer FROM {table}")},
                {("choice", None)},
                table,
            )

    async def test_scores_and_grades_are_untouched(self):
        finished = await self.rows("SELECT score, max_score FROM attempts WHERE id = 'finished'")
        self.assertEqual(finished, [{"score": 2.0, "max_score": 3.0}])
        self.assertEqual(len(await self.rows("SELECT * FROM attempt_results")), 2)
        self.assertEqual(await self.rows("SELECT * FROM attempt_text_answers"), [])
        self.assertEqual(await self.rows("PRAGMA foreign_key_check"), [])

    async def test_kind_is_choice_or_subjective(self):
        await self.insert_fails(
            "INSERT INTO questions (set_id, position, prompt, points, kind) VALUES (3, 9, 'Q', 1, 'essay')"
        )
        await self.insert_fails("UPDATE attempt_questions SET kind = 'essay'")

    async def test_a_typed_answer_is_at_most_10000_characters(self):
        [paper_question] = await self.rows(
            "SELECT id FROM attempt_questions WHERE attempt_id = 'paused' AND position = 0"
        )
        insert = (
            "INSERT INTO attempt_text_answers (attempt_id, attempt_question_id, body, saved_at) "
            "VALUES ('paused', ?, ?, 1)"
        )
        await self.insert_fails(insert, paper_question["id"], "x" * 10_001)
        await self.db.prepare(insert).bind(paper_question["id"], "é" * 10_000).run()
        await self.insert_fails(insert, paper_question["id"], "again")  # one row per question
        await self.insert_fails(insert.replace("'paused'", "'no-such-attempt'"), paper_question["id"], "x")


SHUFFLE_SEED = """
INSERT INTO quiz_sets (id, topic_id, subtopic_id, difficulty, style, seq, title, description,
  time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers,
  max_attempts, status, created_by, created_at, updated_at) VALUES
  (8, 1, 1, 'easy', 'standard', 1, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (24, 1, 1, 'medium', 'standard', 1, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1);
INSERT INTO questions (id, set_id, position, prompt, explanation, points) VALUES
  (80, 8, 0, 'Plain?', 'Nothing here names an option by place.', 1),
  (240, 24, 0, 'What does k1 control?',
   'Term-frequency saturation. Option B describes the b parameter (length normalization).', 1);
"""


class ShuffleOnMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0006 turns both shuffle switches on for every set, except the live sets whose
    explanations name options by position, which keep option order."""

    async def asyncSetUp(self):
        db = SqliteD1(":memory:")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name == "0003_attempt_papers.sql":
                db.executescript(SEED)
            if path.name == "0006_shuffle_on.sql":
                db.executescript(SHUFFLE_SEED)
            db.executescript(path.read_text())
        self.db = db

    async def flags(self):
        rows = (await self.db.prepare(
            "SELECT id, shuffle_questions, shuffle_options FROM quiz_sets ORDER BY id"
        ).all()).results
        return {r["id"]: (r["shuffle_questions"], r["shuffle_options"]) for r in rows}

    async def test_existing_sets_are_turned_on(self):
        flags = await self.flags()
        self.assertEqual(flags[3], (1, 1))

    async def test_an_exception_keeps_option_order_only_where_its_text_is(self):
        flags = await self.flags()
        self.assertEqual(flags[24], (1, 0))  # its explanation names "Option B"
        self.assertEqual(flags[8], (1, 1))   # id on the exception list, but not that set's text

    async def test_attempts_are_untouched(self):
        rows = (await self.db.prepare("SELECT id, status, score FROM attempts ORDER BY id").all()).results
        self.assertEqual([(r["id"], r["status"], r["score"]) for r in rows],
                         [("finished", "submitted", 2.0), ("paused", "in_progress", None)])
        self.assertEqual((await self.db.prepare("PRAGMA foreign_key_check").all()).results, [])


if __name__ == "__main__":
    unittest.main()
