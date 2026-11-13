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


# Live texts 0007 rewrites (its guards), plus look-alikes it must leave alone.
SET6_Q64 = (
    "Correct: it generalizes away dates, times and quantities while keeping the narrative, the topic "
    "and the named entities -- a summary keeps what the story was about and abstracts away the exact "
    "values, which is why the useful compactor rule is specific ('preserve dates, times and quantities "
    "verbatim') rather than vague ('keep the important bits'). Wrong: the first option inverts that, "
    "claiming exact quantities survive while the narrative goes. The third claims the relational "
    "structure linking events is lost, but relational and event structure is exactly what a summary "
    "preserves. And the fourth claims numbers survive because they are short, which confuses token "
    "cost with what a summary chooses to keep."
)
SET24_Q1014 = (
    "k1 calibrates term-frequency scaling: a value of 0 gives a binary (present/absent) model, and a "
    "large value approaches raw term frequency. Option B describes the b parameter (length "
    "normalization), option C describes the IDF component, and option D is a retrieval top-k setting "
    "rather than a BM25 scoring parameter."
)
SET24_Q1014_AFTER = (
    "k1 calibrates term-frequency scaling: a value of 0 gives a binary (present/absent) model, and a "
    "large value approaches raw term frequency. The document-length option describes the b parameter "
    "(length normalization), the query-term-rarity option describes the IDF component, and the "
    "maximum-number-of-documents option is a retrieval top-k setting rather than a BM25 scoring parameter."
)
# Question 1015's live text with one edit, as if an author had touched it since: 0007 must skip it.
SET24_Q1015_EDITED = (
    "b scales length normalization (edited). Option B describes k1 (term-frequency saturation), "
    "option C describes the IDF component, and option D is a preprocessing choice (stopword/stemmer "
    "configuration) rather than b."
)
SET12_NUMBERED = (
    "Attribution held, faithfulness failed. Option 2 inverts the two; option 3 is wrong because "
    "attribution genuinely held; option 4 is a red herring."
)


def _sql(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


EXPLANATIONS_SEED = f"""
INSERT INTO quiz_sets (id, topic_id, subtopic_id, difficulty, style, seq, title, description,
  time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers,
  max_attempts, status, created_by, created_at, updated_at) VALUES
  (6, 1, 1, 'easy', 'standard', 1, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (24, 1, 1, 'medium', 'standard', 1, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (12, 1, 1, 'hard', 'standard', 2, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (34, 1, 1, 'hard', 'standard', 3, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1);
INSERT INTO questions (id, set_id, position, prompt, explanation, points) VALUES
  (64, 6, 0, 'What does a summarizer lose?', {_sql(SET6_Q64)}, 1),
  (65, 6, 1, 'Unrelated?', 'Nothing here names an option by place.', 1),
  (1014, 24, 0, 'What does k1 control?', {_sql(SET24_Q1014)}, 1),
  (1015, 24, 1, 'What does b control?', {_sql(SET24_Q1015_EDITED)}, 1),
  (360, 12, 0, 'Attribution or faithfulness?', {_sql(SET12_NUMBERED)}, 1),
  (1597, 34, 0, 'Plain?', 'Nothing here numbers an option.', 1);
-- the paper of an attempt that was served set 6 in authored order
INSERT INTO attempt_questions (id, attempt_id, source_question_id, position, prompt, explanation, points)
  VALUES (900, 'finished', 64, 9, 'What does a summarizer lose?', {_sql(SET6_Q64)}, 1);
"""


class ExplanationsByContentMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0007 rewrites the explanations that name options by position in the sets 0006 left
    unshuffled, turns their option shuffle on once none is left, and turns option shuffle
    back off for the sets that number their options."""

    async def asyncSetUp(self):
        db = SqliteD1(":memory:")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name == "0003_attempt_papers.sql":
                db.executescript(SEED)
            if path.name == "0006_shuffle_on.sql":
                db.executescript(EXPLANATIONS_SEED)
            db.executescript(path.read_text())
        self.db = db

    async def explanation(self, table, row_id):
        rows = (await self.db.prepare(f"SELECT explanation FROM {table} WHERE id = ?").bind(row_id).all()).results
        return rows[0]["explanation"]

    async def flags(self):
        rows = (await self.db.prepare(
            "SELECT id, shuffle_questions, shuffle_options FROM quiz_sets ORDER BY id"
        ).all()).results
        return {r["id"]: (r["shuffle_questions"], r["shuffle_options"]) for r in rows}

    async def test_a_flagged_explanation_names_the_options_by_content(self):
        self.assertEqual(await self.explanation("questions", 1014), SET24_Q1014_AFTER)
        q64 = await self.explanation("questions", 64)
        for phrase in ("the first option", "The third claims", "the fourth claims"):
            self.assertNotIn(phrase, q64)
        self.assertIn("Wrong: the option keeping dates, times and quantities exactly inverts that", q64)
        self.assertTrue(q64.startswith(SET6_Q64.split(" Wrong:")[0]))  # the rest is unchanged

    async def test_unrelated_and_already_edited_explanations_are_left_alone(self):
        self.assertEqual(await self.explanation("questions", 65), "Nothing here names an option by place.")
        self.assertEqual(await self.explanation("questions", 1015), SET24_Q1015_EDITED)

    async def test_option_shuffle_goes_on_only_where_no_position_reference_is_left(self):
        flags = await self.flags()
        self.assertEqual(flags[6], (1, 1))   # its one flagged explanation was rewritten
        self.assertEqual(flags[24], (1, 0))  # 1015 still says "Option B describes k1"
        self.assertEqual(flags[3], (1, 1))   # not on any list

    async def test_sets_that_number_their_options_keep_option_order(self):
        flags = await self.flags()
        self.assertEqual(flags[12], (1, 0))  # "Option 2 inverts the two; option 3 …"
        self.assertEqual(flags[34], (1, 1))  # id on the list, but not that set's text

    async def test_past_papers_keep_the_text_they_were_served(self):
        self.assertEqual(await self.explanation("attempt_questions", 900), SET6_Q64)

    async def test_running_it_again_changes_nothing(self):
        before = (await self.db.prepare("SELECT id, explanation FROM questions ORDER BY id").all()).results
        flags = await self.flags()
        self.db.executescript((MIGRATIONS / "0007_explanations_by_content.sql").read_text())
        after = (await self.db.prepare("SELECT id, explanation FROM questions ORDER BY id").all()).results
        self.assertEqual([dict(r) for r in after], [dict(r) for r in before])
        self.assertEqual(await self.flags(), flags)


# Live texts 0008 rewrites (its guards), the texts it writes, and an edited look-alike.
SET12_Q360 = (
    "Attribution only asks whether a source exists that the claim points at — and here the source "
    "really exists, so attribution held. Faithfulness asks whether that source entails the claim — it "
    "does not, so faithfulness failed. Option 2 inverts the two; option 3 is wrong because attribution "
    "genuinely held; option 4 is a red herring, since latency is unrelated to whether the cited source "
    "supports the answer."
)
SET12_Q360_AFTER = (
    "Attribution only asks whether a source exists that the claim points at — and here the source "
    "really exists, so attribution held. Faithfulness asks whether that source entails the claim — it "
    "does not, so faithfulness failed. The 'faithfulness held, but attribution failed' option inverts "
    "the two; the 'both failed' option is wrong because attribution genuinely held; the "
    "retrieval-latency option is a red herring, since latency is unrelated to whether the cited source "
    "supports the answer."
)
SET19_Q765 = (
    "Temperature scaling fits T to fix miscalibration; sampling temperature sets T and treats the "
    "entropy as the product — same function, opposite goals. They're not interchangeable, the effects "
    "are reversed in the second distractor, and both involve a scalar."
)
SET19_Q765_AFTER = (
    "Temperature scaling fits T to fix miscalibration; sampling temperature sets T and treats the "
    "entropy as the product — same function, opposite goals. They're not interchangeable, the effects "
    "are reversed in the option where the calibration use makes output more varied, and both involve "
    "a scalar."
)
SET34_Q1597 = (
    "The passthrough key itself is still camelCased (`runtimeVarOverrides`); only its value's keys are "
    "preserved. `extra_info` is not a passthrough field, so `POD_NAME` → `\"POD\" + \"Name\"` = `PODName`, "
    "because `capitalize()` lowercases everything after the first letter. That mangling is exactly why "
    "SLX var names need the passthrough set. Option 2 has no passthrough. Option 3 wrongly preserves the "
    "outer key. Option 4 wrongly treats `POD_NAME` as preserved."
)
# Question 1602's live text with one edit, as if an author had touched it since: 0008 must skip it.
SET34_Q1602_EDITED = (
    "Narrowing on the literal `type` removes the handled members (edited). Option 2 describes today's "
    "untyped behaviour."
)

NUMBERED_SEED = f"""
INSERT INTO quiz_sets (id, topic_id, subtopic_id, difficulty, style, seq, title, description,
  time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers,
  max_attempts, status, created_by, created_at, updated_at) VALUES
  (12, 1, 1, 'hard', 'standard', 2, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (19, 1, 1, 'hard', 'standard', 3, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1),
  (34, 1, 1, 'hard', 'standard', 4, NULL, NULL, NULL, 'partial', 0, 0, 1, NULL, 'published', 'a@x.com', 1, 1);
INSERT INTO questions (id, set_id, position, prompt, explanation, points) VALUES
  (360, 12, 0, 'Attribution or faithfulness?', {_sql(SET12_Q360)}, 1),
  (361, 12, 1, 'Unrelated?', 'Nothing here numbers an option.', 1),
  (765, 19, 0, 'Calibration or sampling?', {_sql(SET19_Q765)}, 1),
  (1597, 34, 0, 'What does this print?', {_sql(SET34_Q1597)}, 1),
  (1602, 34, 1, 'What happens with this renderer?', {_sql(SET34_Q1602_EDITED)}, 1);
-- the paper of an attempt that was served set 12 in authored order
INSERT INTO attempt_questions (id, attempt_id, source_question_id, position, prompt, explanation, points)
  VALUES (901, 'finished', 360, 9, 'Attribution or faithfulness?', {_sql(SET12_Q360)}, 1);
"""


class NumberedExplanationsByContentMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0008 rewrites the explanations that number their options in sets 12 and 34 (and one
    in set 19), and turns option shuffle back on for 12 and 34 once none is left."""

    async def asyncSetUp(self):
        db = SqliteD1(":memory:")
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name == "0003_attempt_papers.sql":
                db.executescript(SEED)
            if path.name == "0006_shuffle_on.sql":
                db.executescript(NUMBERED_SEED)
            db.executescript(path.read_text())
        self.db = db

    async def explanation(self, table, row_id):
        rows = (await self.db.prepare(f"SELECT explanation FROM {table} WHERE id = ?").bind(row_id).all()).results
        return rows[0]["explanation"]

    async def flags(self):
        rows = (await self.db.prepare(
            "SELECT id, shuffle_questions, shuffle_options FROM quiz_sets ORDER BY id"
        ).all()).results
        return {r["id"]: (r["shuffle_questions"], r["shuffle_options"]) for r in rows}

    async def test_a_numbered_explanation_names_the_options_by_content(self):
        self.assertEqual(await self.explanation("questions", 360), SET12_Q360_AFTER)
        q1597 = await self.explanation("questions", 1597)
        for phrase in ("Option 2", "Option 3", "Option 4"):
            self.assertNotIn(phrase, q1597)
        self.assertTrue(q1597.startswith(SET34_Q1597.split(" Option 2")[0]))  # the rest is unchanged

    async def test_the_second_distractor_in_set_19_is_named_by_content(self):
        self.assertEqual(await self.explanation("questions", 765), SET19_Q765_AFTER)
        self.assertEqual((await self.flags())[19], (1, 1))  # it already shuffled its options

    async def test_unrelated_and_already_edited_explanations_are_left_alone(self):
        self.assertEqual(await self.explanation("questions", 361), "Nothing here numbers an option.")
        self.assertEqual(await self.explanation("questions", 1602), SET34_Q1602_EDITED)

    async def test_option_shuffle_goes_back_on_only_where_no_numbered_option_is_left(self):
        flags = await self.flags()
        self.assertEqual(flags[12], (1, 1))  # its numbered explanation was rewritten
        self.assertEqual(flags[34], (1, 0))  # 1602 still says "Option 2 describes …"

    async def test_past_papers_keep_the_text_they_were_served(self):
        self.assertEqual(await self.explanation("attempt_questions", 901), SET12_Q360)

    async def test_running_it_again_changes_nothing(self):
        before = (await self.db.prepare("SELECT id, explanation FROM questions ORDER BY id").all()).results
        flags = await self.flags()
        self.db.executescript((MIGRATIONS / "0008_explanations_by_content_numbered.sql").read_text())
        after = (await self.db.prepare("SELECT id, explanation FROM questions ORDER BY id").all()).results
        self.assertEqual([dict(r) for r in after], [dict(r) for r in before])
        self.assertEqual(await self.flags(), flags)


class SubjectiveMarkingMigrationTest(unittest.IsolatedAsyncioTestCase):
    """0009 adds the marking scheme beside what exists; no stored score or grade moves."""

    async def asyncSetUp(self):
        self.db = _pre_migration_db()
        self.repo = D1AttemptRepository(self.db)

    async def rows(self, sql, *params):
        return [dict(r) for r in (await self.db.prepare(sql).bind(*params).all()).results]

    async def fails(self, sql, *params):
        with self.assertRaises(Exception) as caught:
            await self.db.prepare(sql).bind(*params).run()
        self.assertIn("constraint failed", str(caught.exception))

    async def test_existing_attempts_stay_unmarked_with_their_scores(self):
        self.assertEqual({r["subjective_marks"] for r in await self.rows("SELECT subjective_marks FROM attempts")},
                         {None})
        finished = await self.rows("SELECT score, max_score FROM attempts WHERE id = 'finished'")
        self.assertEqual(finished, [{"score": 2.0, "max_score": 3.0}])
        self.assertEqual(await self.repo.text_marks("finished"), {})
        self.assertEqual(await self.rows("SELECT key_points FROM questions WHERE key_points IS NOT NULL"), [])
        self.assertEqual(await self.rows("PRAGMA foreign_key_check"), [])

    async def test_a_mark_is_never_negative_never_over_its_maximum_and_only_marked_earns(self):
        [question] = await self.rows("SELECT id FROM attempt_questions WHERE attempt_id = 'finished' LIMIT 1")
        insert = ("INSERT INTO attempt_text_marks (attempt_id, attempt_question_id, status, max_marks, awarded) "
                  "VALUES ('finished', ?, ?, 4, ?)")
        await self.fails(insert, question["id"], "marked", -1)
        await self.fails(insert, question["id"], "marked", 4.5)
        await self.fails(insert, question["id"], "flagged", 2)
        await self.fails(insert, question["id"], "graded", 0)
        await self.db.prepare(insert).bind(question["id"], "marked", 3).run()
        await self.fails(insert, question["id"], "marked", 1)  # one row per question

    async def test_a_ledger_row_and_an_entry_hold_their_checks(self):
        await self.fails(
            "INSERT INTO evaluation_calls (token, provider, model, attempt_id, user_email, trigger, day, month, "
            "reserved_micros, rubric, created_at) VALUES ('t', 'p', 'm', 'a', 'e', 'cron', 'd', 'm', 0, 'r', 1)"
        )
        await self.fails(
            "INSERT INTO evaluator_models (provider, model, position, monthly_budget_micros, input_price_per_mtok, "
            "output_price_per_mtok, created_at, updated_at) VALUES ('p', 'm', 0, -1, 0, 0, 1, 1)"
        )


if __name__ == "__main__":
    unittest.main()
