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


MIGRATIONS = BACKEND / "migrations"


def fresh_db():
    """A migrated, empty ``SqliteD1`` over ``:memory:``."""
    from quiz_app.d1.sqlite_binding import SqliteD1

    db = SqliteD1(":memory:")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        db.executescript(path.read_text())
    return db


def sample_import(**overrides) -> dict:
    """A valid import payload (spec section 4): RAG > Embeddings and vector space, 3 questions.

    Keyword overrides replace top-level keys, e.g. ``sample_import(difficulty="easy")``.
    """
    payload = {
        "topic": {"slug": "rag", "name": "RAG"},
        "subtopic": {"slug": "embeddings", "name": "Embeddings and vector space"},
        "difficulty": None,
        "style": "standard",
        "time_limit_minutes": 15,
        "scoring_policy": "all_or_nothing",
        "questions": [
            {
                "prompt": "Which of these change when you swap the embedding model?",
                "explanation": "Vectors from different models are not comparable.",
                "options": [
                    {"body": "Every stored vector must be re-embedded", "correct": True},
                    {"body": "The vector dimension may change", "correct": True},
                    {"body": "The chunking boundaries", "correct": False},
                    {"body": "Similarity thresholds need re-tuning", "correct": True},
                ],
            },
            {
                "prompt": "Which similarity measures are common for text embeddings?",
                "explanation": "Cosine and dot product are the usual choices.",
                "points": 2,
                "options": [
                    {"body": "Cosine similarity", "correct": True},
                    {"body": "Dot product", "correct": True},
                    {"body": "Levenshtein distance", "correct": False},
                ],
            },
            {
                "prompt": "What does normalising embeddings to unit length change?",
                "explanation": None,
                "options": [
                    {"body": "Dot product equals cosine similarity", "correct": True},
                    {"body": "The dimension drops by one", "correct": False},
                ],
            },
        ],
    }
    payload.update(overrides)
    return payload
