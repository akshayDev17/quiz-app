"""D1-backed reads: the solver's catalog (published sets, no answers) and the answer key."""

from __future__ import annotations

from ..models import (
    OptionForSolver,
    QuestionForSolver,
    QuestionKey,
    QuizSetInfo,
    ReviewOption,
    ReviewQuestion,
)
from ..ports import AnswerKeyReader, QuizCatalog
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

    async def set_for_attempt(self, set_id: int) -> QuizSetInfo | None:
        # Any status: archiving a set must not strand or hide attempts already on it.
        row = await self._db.prepare(f"{QUIZ_SET_SELECT} WHERE s.id = ?").bind(set_id).first()
        return quiz_set_from_row(row) if row else None

    async def questions_for_solver(self, set_id: int) -> list[QuestionForSolver]:
        # Deliberately selects neither is_correct nor explanation: a solver-facing
        # read cannot leak what it never fetched.
        rows = (await self._db.prepare(
            "SELECT q.id AS question_id, q.prompt, o.id AS option_id, o.body "
            "FROM questions q JOIN options o ON o.question_id = q.id "
            "WHERE q.set_id = ? ORDER BY q.position, o.position"
        ).bind(set_id).all()).results
        prompts: dict[int, str] = {}
        options: dict[int, list[OptionForSolver]] = {}
        for row in rows:
            prompts[row["question_id"]] = row["prompt"]
            options.setdefault(row["question_id"], []).append(OptionForSolver(row["option_id"], row["body"]))
        return [QuestionForSolver(qid, prompts[qid], tuple(opts)) for qid, opts in options.items()]


class D1AnswerKey(AnswerKeyReader):
    def __init__(self, db):
        self._db = db

    async def answer_key(self, set_id: int) -> list[QuestionKey]:
        rows = (await self._db.prepare(
            "SELECT q.id AS question_id, q.points, o.id AS option_id, o.is_correct "
            "FROM questions q JOIN options o ON o.question_id = q.id "
            "WHERE q.set_id = ? ORDER BY q.position, o.position"
        ).bind(set_id).all()).results
        points: dict[int, float] = {}
        correct: dict[int, set[int]] = {}
        for row in rows:
            points[row["question_id"]] = row["points"]
            correct.setdefault(row["question_id"], set())
            if row["is_correct"]:
                correct[row["question_id"]].add(row["option_id"])
        return [QuestionKey(qid, points[qid], frozenset(ids)) for qid, ids in correct.items()]

    async def review_questions(self, set_id: int) -> list[ReviewQuestion]:
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
