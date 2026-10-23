"""D1-backed attempts: the attempt rows, what the solver ticked, and the graded results."""

from __future__ import annotations

from ..models import Attempt, GradeResult, QuestionResult
from ..ports import AttemptRepository

_SELECT = (
    "SELECT id, set_id, user_email, started_at, deadline_at, finished_at, status, score, max_score "
    "FROM attempts"
)


def _attempt(row: dict) -> Attempt:
    return Attempt(
        id=row["id"],
        set_id=row["set_id"],
        user_email=row["user_email"],
        started_at=row["started_at"],
        deadline_at=row["deadline_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        score=row["score"],
        max_score=row["max_score"],
    )


class D1AttemptRepository(AttemptRepository):
    def __init__(self, db):
        self._db = db

    async def create(self, attempt: Attempt) -> Attempt:
        try:
            await self._db.prepare(
                "INSERT INTO attempts (id, set_id, user_email, started_at, deadline_at, status) "
                "VALUES (?, ?, ?, ?, ?, 'in_progress')"
            ).bind(
                attempt.id, attempt.set_id, attempt.user_email, attempt.started_at, attempt.deadline_at
            ).run()
        except Exception as e:
            # sqlite3.IntegrityError locally; D1 raises its own error with the same message.
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

    async def selections(self, attempt_id: str) -> dict[int, frozenset[int]]:
        rows = (await self._db.prepare(
            "SELECT question_id, option_id FROM attempt_selections WHERE attempt_id = ?"
        ).bind(attempt_id).all()).results
        picked: dict[int, set[int]] = {}
        for row in rows:
            picked.setdefault(row["question_id"], set()).add(row["option_id"])
        return {qid: frozenset(ids) for qid, ids in picked.items()}

    async def replace_selection(self, attempt_id: str, question_id: int, option_ids: frozenset[int]) -> None:
        statements = [
            self._db.prepare(
                "DELETE FROM attempt_selections WHERE attempt_id = ? AND question_id = ?"
            ).bind(attempt_id, question_id)
        ]
        insert = self._db.prepare(
            "INSERT INTO attempt_selections (attempt_id, question_id, option_id) VALUES (?, ?, ?)"
        )
        statements += [insert.bind(attempt_id, question_id, oid) for oid in sorted(option_ids)]
        await self._db.batch(statements)

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
            "INSERT INTO attempt_results (attempt_id, question_id, awarded_points, is_correct) "
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
            "SELECT question_id, awarded_points, is_correct FROM attempt_results WHERE attempt_id = ?"
        ).bind(attempt_id).all()).results
        return {
            row["question_id"]: QuestionResult(row["question_id"], row["awarded_points"], bool(row["is_correct"]))
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
            f"{_SELECT} WHERE user_email = ? AND status <> 'in_progress' ORDER BY finished_at, started_at, rowid"
        ).bind(email).all()).results
        # Ascending, so the latest finished attempt per set is the one left standing.
        return {row["set_id"]: _attempt(row) for row in rows}
