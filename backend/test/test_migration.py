"""0003 backfills papers for attempts that already exist in a live database.

The migration is the only part of this change that touches data it did not create,
so it gets its own test: build a pre-0003 database by hand, seed it the way the old
schema would have, apply 0003, and check both that nothing was lost and that the
result is usable through the repositories.
"""

from __future__ import annotations

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


def _pre_migration_db() -> SqliteD1:
    db = SqliteD1(":memory:")
    for name in ("0001_init.sql", "0002_pause.sql"):
        db.executescript((MIGRATIONS / name).read_text())
    db.executescript(SEED)
    db.executescript((MIGRATIONS / "0003_attempt_papers.sql").read_text())
    return db


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


if __name__ == "__main__":
    unittest.main()
