"""Shared test setup: puts the backend root on sys.path and builds a fresh DB.

Import this first in a test file (or do the same two lines inline) so that
`import quiz_app` resolves whether run as `python3 test/test_x.py` or pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def fresh_db():
    """Return a migrated, empty ``SqliteD1``. Implemented in Task 3."""
    raise NotImplementedError("Task 3")
