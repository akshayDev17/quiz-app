"""D1-backed attempts: the attempt row, its paper, what the solver ticked, the grade.

The paper (``attempt_questions``/``attempt_options``) is written once, at start, and
is the only thing the solver, the grader and the review ever read. Nothing here
joins to ``quiz_sets``/``questions``/``options``, so a set can be edited or deleted
without touching an attempt.
"""

from __future__ import annotations

from ..models import (
    Attempt,
    GradeResult,
    OptionForSolver,
    QuestionForSolver,
    QuestionKey,
    QuestionResult,
    ReviewOption,
    ReviewQuestion,
)
from ..ports import AttemptRepository

_COLUMNS = (
    "id, set_id, user_email, topic_name, subtopic_name, difficulty, style, seq, title, "
    "scoring_policy, reveal_answers, started_at, deadline_at, finished_at, status, "
    "score, max_score, paused_at"
)
_SELECT = f"SELECT {_COLUMNS} FROM attempts"


def _attempt(row: dict) -> Attempt:
    return Attempt(
        id=row["id"],
        set_id=row["set_id"],
        user_email=row["user_email"],
        topic_name=row["topic_name"],
        subtopic_name=row["subtopic_name"],
        difficulty=row["difficulty"],
        style=row["style"],
        seq=row["seq"],
        title=row["title"],
        scoring_policy=row["scoring_policy"],
        reveal_answers=bool(row["reveal_answers"]),
        started_at=row["started_at"],
        deadline_at=row["deadline_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        score=row["score"],
        max_score=row["max_score"],
        paused_at=row["paused_at"],
    )


# The paper, joined once: question columns first, then the option's.
_PAPER = (
    "SELECT aq.id AS question_id, aq.position AS question_position, aq.prompt, "
    "aq.explanation, aq.points, ao.id AS option_id, ao.body, ao.is_correct "
    "FROM attempt_questions aq JOIN attempt_options ao ON ao.attempt_question_id = aq.id "
    "WHERE aq.attempt_id = ? ORDER BY aq.position, ao.position"
)


class D1AttemptRepository(AttemptRepository):
    def __init__(self, db):
        self._db = db

    async def create(self, attempt: Attempt, paper: list[ReviewQuestion]) -> Attempt:
        statements = [self._db.prepare(
            f"INSERT INTO attempts ({_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'in_progress', NULL, NULL, NULL)"
        ).bind(
            attempt.id, attempt.set_id, attempt.user_email, attempt.topic_name,
            attempt.subtopic_name, attempt.difficulty, attempt.style, attempt.seq,
            attempt.title, attempt.scoring_policy, int(attempt.reveal_answers),
            attempt.started_at, attempt.deadline_at,
        )]
        # Options find their question by (attempt_id, position): the question row was
        # inserted earlier in this same batch, so no id has to be read back.
        for position, question in enumerate(paper):
            statements.append(self._db.prepare(
                "INSERT INTO attempt_questions "
                "(attempt_id, source_question_id, position, prompt, explanation, points) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ).bind(
                attempt.id, question.id, position, question.prompt,
                question.explanation, question.points,
            ))
            for option_position, option in enumerate(question.options):
                statements.append(self._db.prepare(
                    "INSERT INTO attempt_options "
                    "(attempt_question_id, source_option_id, position, body, is_correct) "
                    "SELECT aq.id, ?, ?, ?, ? FROM attempt_questions aq "
                    "WHERE aq.attempt_id = ? AND aq.position = ?"
                ).bind(
                    option.id, option_position, option.body, int(option.is_correct),
                    attempt.id, position,
                ))
        try:
            await self._db.batch(statements)
        except Exception as e:
            # sqlite3.IntegrityError locally; D1 raises its own error with the same message.
            # uq_attempts_one_open: somebody already has this set open — hand theirs back.
            if "UNIQUE constraint failed" not in str(e):
                raise
            existing = await self.open_for(attempt.set_id, attempt.user_email)
            if existing is None:
                raise
            return existing
        return attempt

    async def get(self, attempt_id: str) -> Attempt | None:
        row = await self._db.prepare(f"{_SELECT} WHERE id = ?").bind(attempt_id).first()
        return _attempt(row) if row else None

    async def open_for(self, set_id: int, email: str) -> Attempt | None:
        row = await self._db.prepare(
            f"{_SELECT} WHERE set_id = ? AND user_email = ? AND status = 'in_progress'"
        ).bind(set_id, email).first()
        return _attempt(row) if row else None

    async def count_finished(self, set_id: int, email: str) -> int:
        row = await self._db.prepare(
            "SELECT COUNT(*) AS n FROM attempts "
            "WHERE set_id = ? AND user_email = ? AND status <> 'in_progress'"
        ).bind(set_id, email).first()
        return row["n"]

    # -- the paper -----------------------------------------------------------

    async def paper(self, attempt_id: str) -> list[QuestionForSolver]:
        # Deliberately selects neither is_correct nor explanation: the solver-facing
        # read cannot leak what it never fetched.
        rows = (await self._db.prepare(
            "SELECT aq.id AS question_id, aq.prompt, ao.id AS option_id, ao.body "
            "FROM attempt_questions aq JOIN attempt_options ao ON ao.attempt_question_id = aq.id "
            "WHERE aq.attempt_id = ? ORDER BY aq.position, ao.position"
        ).bind(attempt_id).all()).results
        prompts: dict[int, str] = {}
        options: dict[int, list[OptionForSolver]] = {}
        for row in rows:
            prompts[row["question_id"]] = row["prompt"]
            options.setdefault(row["question_id"], []).append(
                OptionForSolver(row["option_id"], row["body"])
            )
        return [QuestionForSolver(qid, prompts[qid], tuple(opts)) for qid, opts in options.items()]

    async def answer_key(self, attempt_id: str) -> list[QuestionKey]:
        rows = (await self._db.prepare(_PAPER).bind(attempt_id).all()).results
        points: dict[int, float] = {}
        correct: dict[int, set[int]] = {}
        for row in rows:
            points[row["question_id"]] = row["points"]
            correct.setdefault(row["question_id"], set())
            if row["is_correct"]:
                correct[row["question_id"]].add(row["option_id"])
        return [QuestionKey(qid, points[qid], frozenset(ids)) for qid, ids in correct.items()]

    async def review(self, attempt_id: str) -> list[ReviewQuestion]:
        rows = (await self._db.prepare(_PAPER).bind(attempt_id).all()).results
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

    # -- what the solver ticked ----------------------------------------------

    async def selections(self, attempt_id: str) -> dict[int, frozenset[int]]:
        rows = (await self._db.prepare(
            "SELECT attempt_question_id, attempt_option_id FROM attempt_selections "
            "WHERE attempt_id = ?"
        ).bind(attempt_id).all()).results
        picked: dict[int, set[int]] = {}
        for row in rows:
            picked.setdefault(row["attempt_question_id"], set()).add(row["attempt_option_id"])
        return {qid: frozenset(ids) for qid, ids in picked.items()}

    def _selection_writes(self, attempt_id: str, answers: dict[int, frozenset[int]]) -> list:
        """Replace each question's rows: one delete, then the inserts."""
        statements = [
            self._db.prepare(
                "DELETE FROM attempt_selections WHERE attempt_id = ? AND attempt_question_id = ?"
            ).bind(attempt_id, question_id)
            for question_id in answers
        ]
        insert = self._db.prepare(
            "INSERT INTO attempt_selections (attempt_id, attempt_question_id, attempt_option_id) "
            "VALUES (?, ?, ?)"
        )
        statements += [
            insert.bind(attempt_id, question_id, option_id)
            for question_id, option_ids in answers.items()
            for option_id in sorted(option_ids)
        ]
        return statements

    async def replace_selection(
        self, attempt_id: str, question_id: int, option_ids: frozenset[int]
    ) -> None:
        await self._db.batch(self._selection_writes(attempt_id, {question_id: option_ids}))

    async def pause(
        self, attempt_id: str, paused_at: int, answers: dict[int, frozenset[int]]
    ) -> None:
        """Freeze the clock and store the answers in the same transaction.

        Both land or neither does: a solver can never end up paused with an answer
        that was never written, which the separate save-then-pause sequence allowed.
        A no-op when already paused (the answers are still written).
        """
        await self._db.batch(self._selection_writes(attempt_id, answers) + [
            self._db.prepare(
                "UPDATE attempts SET paused_at = ? "
                "WHERE id = ? AND status = 'in_progress' AND paused_at IS NULL"
            ).bind(paused_at, attempt_id),
        ])

    async def resume(self, attempt_id: str, now_ms: int) -> None:
        # Extend the deadline by the paused duration; an untimed attempt just unpauses.
        await self._db.prepare(
            "UPDATE attempts SET "
            "deadline_at = CASE WHEN deadline_at IS NULL THEN NULL ELSE deadline_at + (? - paused_at) END, "
            "paused_at = NULL WHERE id = ? AND paused_at IS NOT NULL"
        ).bind(now_ms, attempt_id).run()

    async def finish(self, attempt_id: str, status: str, finished_at: int, grade: GradeResult) -> bool:
        # One batch (one transaction): the results, then the status flip. Every statement is
        # guarded on the attempt still being in_progress, so a second finisher writes nothing,
        # and a failure anywhere leaves the attempt open with no results.
        #
        # Did *this* call finish it? D1's run().meta.changes is unproven on Python Workers, so
        # instead: it was open before the batch, and afterwards the row holds exactly what this
        # call wrote. (Two finishers writing identical values could both see True; they leave
        # the same state, and the service does not act on the result.)
        before = await self.get(attempt_id)
        if before is None or before.status != "in_progress":
            return False
        still_open = "EXISTS (SELECT 1 FROM attempts WHERE id = ? AND status = 'in_progress')"
        insert = self._db.prepare(
            "INSERT INTO attempt_results (attempt_id, attempt_question_id, awarded_points, is_correct) "
            f"SELECT ?, ?, ?, ? WHERE {still_open}"
        )
        statements = [
            insert.bind(attempt_id, r.question_id, r.awarded_points, int(r.is_correct), attempt_id)
            for r in grade.results
        ]
        statements.append(self._db.prepare(
            "UPDATE attempts SET status = ?, finished_at = ?, score = ?, max_score = ? "
            "WHERE id = ? AND status = 'in_progress'"
        ).bind(status, finished_at, grade.score, grade.max_score, attempt_id))
        await self._db.batch(statements)
        after = await self.get(attempt_id)
        return (after.status, after.finished_at, after.score, after.max_score) == (
            status, finished_at, grade.score, grade.max_score
        )

    async def results(self, attempt_id: str) -> dict[int, QuestionResult]:
        rows = (await self._db.prepare(
            "SELECT attempt_question_id, awarded_points, is_correct FROM attempt_results "
            "WHERE attempt_id = ?"
        ).bind(attempt_id).all()).results
        return {
            row["attempt_question_id"]: QuestionResult(
                row["attempt_question_id"], row["awarded_points"], bool(row["is_correct"])
            )
            for row in rows
        }

    async def for_user(self, email: str) -> list[Attempt]:
        rows = (await self._db.prepare(
            f"{_SELECT} WHERE user_email = ? ORDER BY started_at DESC, id"
        ).bind(email).all()).results
        return [_attempt(row) for row in rows]

    async def open_for_user(self, email: str) -> list[Attempt]:
        rows = (await self._db.prepare(
            f"{_SELECT} WHERE user_email = ? AND status = 'in_progress' ORDER BY started_at DESC, id"
        ).bind(email).all()).results
        return [_attempt(row) for row in rows]

    async def last_finished_by_set(self, email: str) -> dict[int, Attempt]:
        rows = (await self._db.prepare(
            f"{_SELECT} WHERE user_email = ? AND status <> 'in_progress' "
            "ORDER BY finished_at, started_at, rowid"
        ).bind(email).all()).results
        # Ascending, so the latest finished attempt per set is the one left standing.
        # A deleted set's attempts key on None and simply match no published card.
        return {row["set_id"]: _attempt(row) for row in rows}
