"""Time limits and grace.

Run:  python3 test/test_timing.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from quiz_app.timing import NoTimeLimit, TimeLimit  # noqa: E402


class TimeLimitTest(unittest.TestCase):
    def test_time_limits(self):
        self.assertEqual(TimeLimit.of(15).deadline(1_000), 1_000 + 15 * 60_000)
        self.assertIsNone(TimeLimit.of(None).deadline(1_000))
        self.assertIsInstance(TimeLimit.of(None), NoTimeLimit)
        with self.assertRaises(ValueError):
            TimeLimit.of(0)


if __name__ == "__main__":
    unittest.main()
