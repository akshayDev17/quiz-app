"""Scoring policies and the factory.

Run:  python3 test/test_scoring.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.errors import Invalid  # noqa: E402
from quiz_app.scoring import MARKING, ScoringPolicyFactory  # noqa: E402

C = frozenset({1, 2, 4})


class ScoringTest(unittest.TestCase):
    def test_all_or_nothing(self):
        p = ScoringPolicyFactory.for_name("all_or_nothing")
        self.assertEqual(p.award(2, C, frozenset({1, 2, 4})), 2)
        self.assertEqual(p.award(2, C, frozenset({1, 2})), 0)
        self.assertEqual(p.award(2, C, frozenset()), 0)

    def test_partial(self):
        p = ScoringPolicyFactory.for_name("partial")
        self.assertAlmostEqual(p.award(3, C, frozenset({1, 2})), 2.0)  # (2-0)/3*3
        self.assertAlmostEqual(p.award(3, C, frozenset({1, 2, 3})), 1.0)  # (2-1)/3*3
        self.assertEqual(p.award(3, C, frozenset({1, 2, 3, 4, 5})), 1.0)  # (3-2)/3*3
        self.assertEqual(p.award(3, C, frozenset({3, 5})), 0)  # floored at 0

    def test_negative_marking(self):
        p = ScoringPolicyFactory.for_name("negative_marking")
        self.assertEqual(p.award(1, C, frozenset({1, 2, 4})), 6)  # all correct ticked: 3 x +2
        self.assertEqual(p.award(1, C, frozenset({1, 2})), 4)  # a correct option left unticked costs nothing
        self.assertEqual(p.award(1, C, frozenset({1, 2, 3})), 3)  # 2 x +2, 1 x -1
        self.assertEqual(p.award(1, C, frozenset({3, 5})), -2)  # only wrong ticks: 2 x -1
        self.assertEqual(p.award(1, C, frozenset({3})), -1)
        self.assertEqual(p.award(1, C, frozenset()), -2)  # not attempted

    def test_negative_marking_ignores_the_question_weight(self):
        p = ScoringPolicyFactory.for_name("negative_marking")
        self.assertEqual(p.award(5, C, frozenset({1})), 2)
        self.assertEqual(p.award(5, C, frozenset()), -2)
        self.assertEqual(p.max_award(5, C), 6)  # +2 per correct option

    def test_older_policies_score_a_blank_zero_and_max_out_at_the_weight(self):
        for name in ("all_or_nothing", "partial"):
            p = ScoringPolicyFactory.for_name(name)
            self.assertEqual(p.award(3, C, frozenset()), 0, name)
            self.assertEqual(p.max_award(3, C), 3, name)

    def test_unknown_policy(self):
        with self.assertRaises(Invalid):
            ScoringPolicyFactory.for_name("negative")

    def test_new_attempts_are_marked_negatively(self):
        self.assertEqual(MARKING, "negative_marking")

    def test_names(self):
        self.assertEqual(ScoringPolicyFactory.names(), frozenset({"all_or_nothing", "partial", "negative_marking"}))


if __name__ == "__main__":
    unittest.main()
