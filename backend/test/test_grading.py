"""Pure grader.

Run:  python3 test/test_grading.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.grading import grade  # noqa: E402
from quiz_app.models import QuestionKey  # noqa: E402
from quiz_app.scoring import AllOrNothing, PartialCredit  # noqa: E402

KEYS = [QuestionKey(10, 1, frozenset({1})), QuestionKey(11, 2, frozenset({3, 4}))]


class GradeTest(unittest.TestCase):
    def test_grade_marks_exact_match_and_sums(self):
        r = grade(KEYS, {10: frozenset({1}), 11: frozenset({3})}, PartialCredit())
        self.assertEqual((r.score, r.max_score), (2.0, 3))
        self.assertEqual([x.is_correct for x in r.results], [True, False])
        self.assertEqual(r.results[1].awarded_points, 1.0)

    def test_blank_question_scores_zero(self):
        r = grade(KEYS, {10: frozenset({1})}, PartialCredit())
        self.assertEqual(r.results[1].awarded_points, 0)
        self.assertFalse(r.results[1].is_correct)
        self.assertEqual(r.score, 1)

    def test_results_follow_key_order(self):
        r = grade(KEYS, {}, AllOrNothing())
        self.assertEqual([x.question_id for x in r.results], [10, 11])
        self.assertEqual((r.score, r.max_score), (0, 3))


if __name__ == "__main__":
    unittest.main()
