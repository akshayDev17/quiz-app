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
from quiz_app.scoring import AllOrNothing, NegativeMarking, PartialCredit  # noqa: E402

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


# q10: one correct option of three; q11: two correct of four.
NEG_KEYS = [QuestionKey(10, 1, frozenset({1})), QuestionKey(11, 1, frozenset({3, 4}))]


class NegativeMarkingGradeTest(unittest.TestCase):
    def grade(self, selections):
        return grade(NEG_KEYS, selections, NegativeMarking())

    def test_all_correct_ticked_scores_the_maximum(self):
        r = self.grade({10: frozenset({1}), 11: frozenset({3, 4})})
        self.assertEqual([x.awarded_points for x in r.results], [2, 4])
        self.assertEqual((r.score, r.max_score), (6, 6))
        self.assertEqual([x.is_correct for x in r.results], [True, True])

    def test_a_mix_of_right_and_wrong_ticks(self):
        r = self.grade({10: frozenset({1, 2}), 11: frozenset({3, 5})})
        self.assertEqual([x.awarded_points for x in r.results], [1, 1])  # +2 -1 each
        self.assertEqual((r.score, r.max_score), (2, 6))
        self.assertEqual([x.is_correct for x in r.results], [False, False])

    def test_only_wrong_ticks(self):
        r = self.grade({10: frozenset({2}), 11: frozenset({1, 2})})
        self.assertEqual([x.awarded_points for x in r.results], [-1, -2])
        self.assertEqual(r.score, -3)

    def test_nothing_ticked_scores_minus_two_a_question(self):
        r = self.grade({})
        self.assertEqual([x.awarded_points for x in r.results], [-2, -2])
        self.assertEqual((r.score, r.max_score), (-4, 6))
        self.assertEqual([x.is_correct for x in r.results], [False, False])

    def test_an_empty_selection_counts_as_not_attempted(self):
        self.assertEqual(self.grade({10: frozenset()}).results[0].awarded_points, -2)

    def test_the_quiz_total_may_go_negative(self):
        r = self.grade({10: frozenset({2, 3})})  # -1 -1 on q10, q11 blank -2
        self.assertEqual(r.score, -4)
        self.assertLess(r.score, 0)


if __name__ == "__main__":
    unittest.main()
