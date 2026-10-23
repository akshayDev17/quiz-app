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
from quiz_app.scoring import ScoringPolicyFactory  # noqa: E402

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

    def test_unknown_policy(self):
        with self.assertRaises(Invalid):
            ScoringPolicyFactory.for_name("negative")

    def test_names(self):
        self.assertEqual(ScoringPolicyFactory.names(), frozenset({"all_or_nothing", "partial"}))


if __name__ == "__main__":
    unittest.main()
