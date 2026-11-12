"""D1-backed catalogue reads: published sets for solvers, and the paper to copy at start.

A private set is left out unless the caller asks for it with ``include_private``.

Nothing here is read once an attempt exists — the attempt's own paper is
(`quiz_app.d1.attempts`), which is what lets a set be edited or deleted freely.
"""

from __future__ import annotations

from ..models import QuizSetInfo, ReviewQuestion
from ..ports import PaperSource, QuizCatalog
from ._rows import QUIZ_SET_SELECT, quiz_set_from_row, review_questions

def _published(include_private: bool) -> str:
    """Published sets; private ones only when asked for (their editors see them)."""
    return "WHERE s.status = 'published'" + ("" if include_private else " AND s.visibility = 'public'")


class D1Catalog(QuizCatalog):
    def __init__(self, db):
        self._db = db

    async def list_published(self, include_private: bool = False) -> list[QuizSetInfo]:
        rows = (await self._db.prepare(
            f"{QUIZ_SET_SELECT} {_published(include_private)} "
            "ORDER BY t.position, t.id, st.position, st.id, s.seq, s.id"
        ).all()).results
        return [quiz_set_from_row(row) for row in rows]

    async def get_set(self, set_id: int, include_private: bool = False) -> QuizSetInfo | None:
        row = await self._db.prepare(
            f"{QUIZ_SET_SELECT} {_published(include_private)} AND s.id = ?"
        ).bind(set_id).first()
        return quiz_set_from_row(row) if row else None


class D1PaperSource(PaperSource):
    def __init__(self, db):
        self._db = db

    async def paper_source(self, set_id: int) -> list[ReviewQuestion]:
        # LEFT JOIN: a subjective question has no options and must still be copied.
        rows = (await self._db.prepare(
            "SELECT q.id AS question_id, q.prompt, q.explanation, q.points, q.kind, q.model_answer, "
            "o.id AS option_id, o.body, o.is_correct "
            "FROM questions q LEFT JOIN options o ON o.question_id = q.id "
            "WHERE q.set_id = ? ORDER BY q.position, o.position"
        ).bind(set_id).all()).results
        return review_questions(rows)

