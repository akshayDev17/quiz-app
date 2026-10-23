"""Attempt-seeded display order.

Run:  python3 test/test_shuffle.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.models import OptionForSolver, QuestionForSolver  # noqa: E402
from quiz_app.shuffle import display_order  # noqa: E402

QS = [
    QuestionForSolver(
        q,
        f"Q{q}",
        tuple(OptionForSolver(q * 10 + o, f"O{q}.{o}") for o in range(1, 6)),
    )
    for q in range(1, 9)
]


class ShuffleTest(unittest.TestCase):
    def test_no_shuffle_keeps_authored_order(self):
        self.assertEqual(display_order("att-1", QS, False, False), QS)

    def test_shuffle_is_deterministic_per_attempt(self):
        a = display_order("att-1", QS, True, True)
        b = display_order("att-1", QS, True, True)
        self.assertEqual(a, b)

    def test_shuffle_differs_across_attempts(self):
        orders = [display_order(f"att-{i}", QS, True, True) for i in range(5)]
        self.assertTrue(any(o != orders[0] for o in orders[1:]))

    def test_shuffle_preserves_contents(self):
        out = display_order("att-1", QS, True, True)
        self.assertEqual(sorted(q.id for q in out), [q.id for q in QS])
        by_id = {q.id: q for q in QS}
        for q in out:
            self.assertEqual(q.prompt, by_id[q.id].prompt)
            self.assertEqual(
                sorted(o.id for o in q.options), sorted(o.id for o in by_id[q.id].options)
            )

    def test_questions_only_leaves_options_in_order(self):
        out = display_order("att-1", QS, True, False)
        by_id = {q.id: q for q in QS}
        self.assertTrue(all(q.options == by_id[q.id].options for q in out))

    def test_options_only_leaves_questions_in_order(self):
        out = display_order("att-1", QS, False, True)
        self.assertEqual([q.id for q in out], [q.id for q in QS])

    def test_input_not_mutated(self):
        snapshot = list(QS)
        display_order("att-1", QS, True, True)
        self.assertEqual(QS, snapshot)


if __name__ == "__main__":
    unittest.main()
