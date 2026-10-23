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


class AttemptTest(unittest.TestCase):
    def test_attempt_due_and_writes(self):
        a = Attempt("a", 1, "u@x.com", 0, 60_000, None, "in_progress", None, None)
        self.assertFalse(a.is_due(59_999)); self.assertTrue(a.is_due(60_000))
        self.assertTrue(a.accepts_writes(69_999, GRACE_MS)); self.assertFalse(a.accepts_writes(70_001, GRACE_MS))
        untimed = Attempt("b", 1, "u@x.com", 0, None, None, "in_progress", None, None)
        self.assertFalse(untimed.is_due(10**15)); self.assertTrue(untimed.accepts_writes(10**15, GRACE_MS))
        self.assertFalse(Attempt("c", 1, "u", 0, None, 5, "submitted", 1, 1).accepts_writes(1, GRACE_MS))

    def test_is_open_only_while_in_progress(self):
        self.assertTrue(Attempt("a", 1, "u", 0, None, None, "in_progress", None, None).is_open)
        self.assertFalse(Attempt("a", 1, "u", 0, None, 5, "submitted", 1, 1).is_open)


class SolverShapeTest(unittest.TestCase):
    def test_solver_question_has_no_answer_fields(self):
        names = {f.name for f in dataclasses.fields(QuestionForSolver)} | {f.name for f in dataclasses.fields(OptionForSolver)}
        self.assertFalse(names & {"is_correct", "correct", "explanation"})


if __name__ == "__main__":
    unittest.main()
