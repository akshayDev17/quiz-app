"""Models: derived set names, attempt timing predicates, solver payload shape.

Run:  python3 test/test_models.py
"""

from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.models import (  # noqa: E402
    Attempt,
    OptionForSolver,
    QuestionForSolver,
    set_name,
)
from quiz_app.timing import GRACE_MS  # noqa: E402


class SetNameTest(unittest.TestCase):
    def test_set_name_variants(self):
        self.assertEqual(set_name("Embeddings and vector space", None, "standard", 1, None), "Embeddings and vector space · Set 1")
        self.assertEqual(set_name("Prefix caching", None, "scenario", 1, None), "Prefix caching · Scenario · Set 1")
        self.assertEqual(set_name(None, "easy", "standard", 2, None), "Easy · Set 2")
        self.assertEqual(set_name("Ranking", "medium", "scenario", 1, None), "Ranking · Medium · Scenario · Set 1")
        self.assertEqual(set_name("Ranking", "medium", "scenario", 1, None, include_subtopic=False), "Medium · Scenario · Set 1")
        self.assertEqual(set_name("Ranking", None, "standard", 1, "Final exam"), "Final exam")


def attempt(**overrides) -> Attempt:
    """An attempt with everything the paper pins filled in; override what a test cares about."""
    fields = dict(
        id="a", set_id=1, user_email="u@x.com", topic_name="RAG", subtopic_name="Ranking",
        difficulty="medium", style="standard", seq=1, title=None,
        scoring_policy="all_or_nothing", reveal_answers=True, started_at=0, deadline_at=None,
        finished_at=None, status="in_progress", score=None, max_score=None,
    )
    fields.update(overrides)
    return Attempt(**fields)


class AttemptTest(unittest.TestCase):
    def test_attempt_due_and_writes(self):
        a = attempt(deadline_at=60_000)
        self.assertFalse(a.is_due(59_999)); self.assertTrue(a.is_due(60_000))
        self.assertTrue(a.accepts_writes(69_999, GRACE_MS)); self.assertFalse(a.accepts_writes(70_001, GRACE_MS))
        untimed = attempt(id="b")
        self.assertFalse(untimed.is_due(10**15)); self.assertTrue(untimed.accepts_writes(10**15, GRACE_MS))
        self.assertFalse(attempt(id="c", status="submitted", finished_at=5, score=1, max_score=1)
                         .accepts_writes(1, GRACE_MS))

    def test_is_open_only_while_in_progress(self):
        self.assertTrue(attempt().is_open)
        self.assertFalse(attempt(status="submitted", finished_at=5, score=1, max_score=1).is_open)

    def test_name_is_the_one_the_attempt_started_under(self):
        # Frozen at start: renaming or deleting the set cannot rewrite it.
        self.assertEqual(attempt().name, "Ranking · Medium · Set 1")
        self.assertEqual(attempt(title="Final exam").name, "Final exam")
        self.assertEqual(attempt(subtopic_name=None, difficulty=None).name, "Set 1")
        self.assertEqual(attempt(set_id=None).name, "Ranking · Medium · Set 1")


class SolverShapeTest(unittest.TestCase):
    def test_solver_question_has_no_answer_fields(self):
        names = {f.name for f in dataclasses.fields(QuestionForSolver)} | {f.name for f in dataclasses.fields(OptionForSolver)}
        self.assertFalse(names & {"is_correct", "correct", "explanation"})


if __name__ == "__main__":
    unittest.main()
