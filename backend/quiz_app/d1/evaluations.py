"""D1-backed evaluation state: the admin's evaluator list, the spend ledger, and the claims
and results on ``attempt_text_marks``.

Two guards make "at most once" and "within budget" hold under concurrent requests, each a
single conditional statement (D1 runs one statement, and one batch, at a time):

* ``claim_awaiting`` stamps a request's token on an attempt's awaiting rows that nobody
  holds, then reads back only the rows carrying that token. Two submits of one attempt
  can never both send the same answer.
* ``reserve`` inserts the ledger row only if this month's spend of that provider · model
  plus the reservation stays within the budget, and the daily quotas still have room.
  A refused insert writes nothing.

Results are written under the claim: a row whose claim moved on is left alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import Conflict, NotFound
from ..models import AWAITING, FLAGGED, MARKED
from ._rows import key_points_from_json


@dataclass(frozen=True)
class EvaluatorModel:
    id: int
    provider: str
    model: str
    position: int
    monthly_budget_micros: int
    input_price_per_mtok: float
    output_price_per_mtok: float


@dataclass(frozen=True)
class ClaimedAnswer:
    question_id: int
    prompt: str
    model_answer: str
    key_points: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Reservation:
    token: str
    provider: str
    model: str
    attempt_id: str
    user_email: str
    trigger: str
    day: str
    month: str
    reserved_micros: int
    rubric: str
    created_at: int


@dataclass(frozen=True)
class Settlement:
    cost_micros: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    http_status: int | None
    request_id: str | None
    outcome: str


_MODEL_COLUMNS = (
    "id, provider, model, position, monthly_budget_micros, input_price_per_mtok, output_price_per_mtok"
)


def _model(row: dict) -> EvaluatorModel:
    return EvaluatorModel(
        id=row["id"], provider=row["provider"], model=row["model"], position=row["position"],
        monthly_budget_micros=row["monthly_budget_micros"],
        input_price_per_mtok=row["input_price_per_mtok"],
        output_price_per_mtok=row["output_price_per_mtok"],
    )


def _placeholders(n: int) -> str:
    return ", ".join("?" for _ in range(n))


class D1EvaluationRepository:
    def __init__(self, db):
        self._db = db

    # -- the admin's list --------------------------------------------------

    async def list_models(self) -> list[EvaluatorModel]:
        rows = (await self._db.prepare(
            f"SELECT {_MODEL_COLUMNS} FROM evaluator_models ORDER BY position, id"
        ).all()).results
        return [_model(row) for row in rows]

    async def get_model(self, model_id: int) -> EvaluatorModel:
        row = await self._db.prepare(
            f"SELECT {_MODEL_COLUMNS} FROM evaluator_models WHERE id = ?"
        ).bind(model_id).first()
        if row is None:
            raise NotFound("evaluator not found")
        return _model(row)

    async def add_model(
        self, provider: str, model: str, budget_micros: int, input_price: float, output_price: float, now: int
    ) -> int:
        try:
            row = await self._db.prepare(
                "INSERT INTO evaluator_models (provider, model, position, monthly_budget_micros, "
                "input_price_per_mtok, output_price_per_mtok, created_at, updated_at) "
                "SELECT ?, ?, COALESCE(MAX(position), -1) + 1, ?, ?, ?, ?, ? FROM evaluator_models "
                "RETURNING id"
            ).bind(provider, model, budget_micros, input_price, output_price, now, now).first()
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise Conflict("that provider and model are already in the list") from None
            raise
        return row["id"]

    async def update_model(
        self, model_id: int, budget_micros: int, input_price: float, output_price: float, now: int
    ) -> None:
        await self.get_model(model_id)
        await self._db.prepare(
            "UPDATE evaluator_models SET monthly_budget_micros = ?, input_price_per_mtok = ?, "
            "output_price_per_mtok = ?, updated_at = ? WHERE id = ?"
        ).bind(budget_micros, input_price, output_price, now, model_id).run()

    async def delete_model(self, model_id: int) -> None:
        await self.get_model(model_id)
        await self._db.prepare("DELETE FROM evaluator_models WHERE id = ?").bind(model_id).run()

    async def reorder(self, ids: list[int], now: int) -> None:
        await self._db.batch([
            self._db.prepare(
                "UPDATE evaluator_models SET position = ?, updated_at = ? WHERE id = ?"
            ).bind(position, now, model_id)
            for position, model_id in enumerate(ids)
        ])

    # -- the ledger ----------------------------------------------------------

    async def month_spend(self, month: str) -> dict[tuple[str, str], int]:
        """This month's tracked spend by (provider, model), in micro-dollars."""
        rows = (await self._db.prepare(
            "SELECT provider, model, SUM(COALESCE(cost_micros, reserved_micros)) AS spent "
            "FROM evaluation_calls WHERE month = ? GROUP BY provider, model"
        ).bind(month).all()).results
        return {(row["provider"], row["model"]): row["spent"] or 0 for row in rows}

    async def calls_today(self, day: str, email: str) -> tuple[int, int]:
        """(every call today, this person's calls today)."""
        row = await self._db.prepare(
            "SELECT COUNT(*) AS everyone, COALESCE(SUM(user_email = ?), 0) AS mine "
            "FROM evaluation_calls WHERE day = ?"
        ).bind(email, day).first()
        return row["everyone"], row["mine"]

    async def reserve(
        self, r: Reservation, budget_micros: int, global_limit: int | None, user_limit: int | None
    ) -> bool:
        """Insert the ledger row only if the budget and the daily quotas allow it (a ``None``
        limit is not enforced). True when it was inserted."""
        await self._db.prepare(
            "INSERT INTO evaluation_calls (token, provider, model, attempt_id, user_email, trigger, "
            "day, month, reserved_micros, rubric, created_at) "
            "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE "
            "(SELECT COALESCE(SUM(COALESCE(cost_micros, reserved_micros)), 0) FROM evaluation_calls "
            " WHERE provider = ? AND model = ? AND month = ?) + ? <= ? "
            "AND (? IS NULL OR (SELECT COUNT(*) FROM evaluation_calls WHERE day = ?) < ?) "
            "AND (? IS NULL OR (SELECT COUNT(*) FROM evaluation_calls WHERE day = ? AND user_email = ?) < ?)"
        ).bind(
            r.token, r.provider, r.model, r.attempt_id, r.user_email, r.trigger, r.day, r.month,
            r.reserved_micros, r.rubric, r.created_at,
            r.provider, r.model, r.month, r.reserved_micros, budget_micros,
            global_limit, r.day, global_limit,
            user_limit, r.day, r.user_email, user_limit,
        ).run()
        row = await self._db.prepare(
            "SELECT 1 AS ok FROM evaluation_calls WHERE token = ?"
        ).bind(r.token).first()
        return row is not None

    async def settle(self, token: str, s: Settlement) -> None:
        await self._db.prepare(
            "UPDATE evaluation_calls SET cost_micros = ?, input_tokens = ?, output_tokens = ?, "
            "latency_ms = ?, http_status = ?, request_id = ?, outcome = ? WHERE token = ?"
        ).bind(
            s.cost_micros, s.input_tokens, s.output_tokens, s.latency_ms, s.http_status,
            s.request_id, s.outcome, token,
        ).run()

    # -- awaiting answers --------------------------------------------------

    async def claim_awaiting(
        self, attempt_id: str, token: str, now: int, stale_before: int | None
    ) -> list[ClaimedAnswer]:
        """Take the attempt's awaiting answers nobody holds (or, with ``stale_before``, whose
        holder claimed them before that time and never finished), in served order."""
        await self._db.prepare(
            "UPDATE attempt_text_marks SET claim = ?, claimed_at = ? "
            "WHERE attempt_id = ? AND status = ? "
            "AND (claim IS NULL OR (? IS NOT NULL AND claimed_at < ?))"
        ).bind(token, now, attempt_id, AWAITING, stale_before, stale_before).run()
        rows = (await self._db.prepare(
            "SELECT m.attempt_question_id, aq.prompt, aq.model_answer, aq.key_points, t.body "
            "FROM attempt_text_marks m "
            "JOIN attempt_questions aq ON aq.id = m.attempt_question_id "
            "JOIN attempt_text_answers t ON t.attempt_id = m.attempt_id "
            " AND t.attempt_question_id = m.attempt_question_id "
            "WHERE m.attempt_id = ? AND m.claim = ? AND m.status = ? ORDER BY aq.position"
        ).bind(attempt_id, token, AWAITING).all()).results
        return [
            ClaimedAnswer(
                question_id=row["attempt_question_id"], prompt=row["prompt"],
                model_answer=row["model_answer"] or "", key_points=key_points_from_json(row["key_points"]),
                text=row["body"],
            )
            for row in rows
        ]

    async def release(self, attempt_id: str, token: str, question_ids: list[int], reason: str | None) -> None:
        """Hand claimed answers back, still awaiting, noting why (for admins)."""
        if not question_ids:
            return
        await self._db.prepare(
            "UPDATE attempt_text_marks SET claim = NULL, claimed_at = NULL, reason = ? "
            f"WHERE attempt_id = ? AND claim = ? AND attempt_question_id IN ({_placeholders(len(question_ids))})"
        ).bind(reason, attempt_id, token, *question_ids).run()

    async def record(
        self,
        attempt_id: str,
        token: str,
        marked: list[tuple[int, int, float, str]],
        flagged: list[tuple[int, str]],
        provider: str | None,
        model: str | None,
        now: int,
    ) -> None:
        """Write verdicts (question id, level, award, feedback) and flags (question id, reason)
        for rows this token still holds, then recompute the attempt's score in the same
        transaction: its choice results plus every subjective award."""
        held = "attempt_id = ? AND attempt_question_id = ? AND claim = ? AND status = ?"
        statements = [
            self._db.prepare(
                "UPDATE attempt_text_marks SET status = ?, level = ?, awarded = ?, feedback = ?, "
                f"reason = NULL, provider = ?, model = ?, claim = NULL, claimed_at = NULL, marked_at = ? WHERE {held}"
            ).bind(MARKED, level, awarded, feedback, provider, model, now,
                   attempt_id, question_id, token, AWAITING)
            for question_id, level, awarded, feedback in marked
        ]
        statements += [
            self._db.prepare(
                "UPDATE attempt_text_marks SET status = ?, awarded = 0, reason = ?, provider = ?, model = ?, "
                f"claim = NULL, claimed_at = NULL, marked_at = ? WHERE {held}"
            ).bind(FLAGGED, reason, provider, model, now, attempt_id, question_id, token, AWAITING)
            for question_id, reason in flagged
        ]
        if not statements:
            return
        statements.append(self._db.prepare(
            "UPDATE attempts SET score = "
            "(SELECT COALESCE(SUM(awarded_points), 0) FROM attempt_results WHERE attempt_id = ?) + "
            "(SELECT COALESCE(SUM(awarded), 0) FROM attempt_text_marks WHERE attempt_id = ?) "
            "WHERE id = ? AND status <> 'in_progress'"
        ).bind(attempt_id, attempt_id, attempt_id))
        await self._db.batch(statements)

    async def attempts_awaiting(self, limit: int, stale_before: int) -> list[str]:
        """Closed attempts with an answer awaiting evaluation that nobody holds (or holds
        stale), oldest first."""
        rows = (await self._db.prepare(
            "SELECT a.id FROM attempts a WHERE a.status <> 'in_progress' AND EXISTS ("
            " SELECT 1 FROM attempt_text_marks m WHERE m.attempt_id = a.id AND m.status = ? "
            " AND (m.claim IS NULL OR m.claimed_at < ?)) "
            "ORDER BY a.finished_at, a.id LIMIT ?"
        ).bind(AWAITING, stale_before, limit).all()).results
        return [row["id"] for row in rows]

    async def queue(self) -> tuple[int, int, dict[str, int]]:
        """(answers awaiting, answers flagged, awaiting by reason)."""
        rows = (await self._db.prepare(
            "SELECT status, COALESCE(reason, 'not yet tried') AS reason, COUNT(*) AS n "
            "FROM attempt_text_marks WHERE status IN (?, ?) GROUP BY status, reason"
        ).bind(AWAITING, FLAGGED).all()).results
        awaiting = sum(r["n"] for r in rows if r["status"] == AWAITING)
        flagged = sum(r["n"] for r in rows if r["status"] == FLAGGED)
        reasons: dict[str, int] = {}
        for r in rows:
            if r["status"] == AWAITING:
                reasons[r["reason"]] = reasons.get(r["reason"], 0) + r["n"]
        return awaiting, flagged, reasons
