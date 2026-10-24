"""D1-backed catalogue reads: published sets for solvers, and the paper to copy at start.

Nothing here is read once an attempt exists — the attempt's own paper is
(`quiz_app.d1.attempts`), which is what lets a set be edited or deleted freely.
"""

from __future__ import annotations

from ..models import QuizSetInfo, ReviewOption, ReviewQuestion
from ..ports import PaperSource, QuizCatalog
from ._rows import QUIZ_SET_SELECT, quiz_set_from_row

_PUBLISHED = "WHERE s.status = 'published'"


class D1Catalog(QuizCatalog):
    def __init__(self, db):
        self._db = db

    async def list_published(self) -> list[QuizSetInfo]:
        rows = (await self._db.prepare(
            f"{QUIZ_SET_SELECT} {_PUBLISHED} "
            "ORDER BY t.position, t.id, st.position, st.id, s.seq, s.id"
        ).all()).results
        return [quiz_set_from_row(row) for row in rows]

    async def get_set(self, set_id: int) -> QuizSetInfo | None:
        row = await self._db.prepare(
            f"{QUIZ_SET_SELECT} {_PUBLISHED} AND s.id = ?"
        ).bind(set_id).first()
        return quiz_set_from_row(row) if row else None


class D1PaperSource(PaperSource):
    def __init__(self, db):
        self._db = db

    async def paper_source(self, set_id: int) -> list[ReviewQuestion]:
        rows = (await self._db.prepare(
            "SELECT q.id AS question_id, q.prompt, q.explanation, q.points, "
            "o.id AS option_id, o.body, o.is_correct "
            "FROM questions q JOIN options o ON o.question_id = q.id "
            "WHERE q.set_id = ? ORDER BY q.position, o.position"
        ).bind(set_id).all()).results
        heads: dict[int, dict] = {}
        options: dict[int, list[ReviewOption]] = {}
        for row in rows:
            heads.setdefault(row["question_id"], row)
            options.setdefault(row["question_id"], []).append(
                ReviewOption(row["option_id"], row["body"], bool(row["is_correct"]))
            )
        return [
            ReviewQuestion(qid, head["prompt"], head["explanation"], head["points"], tuple(options[qid]))
            for qid, head in heads.items()
        ]
