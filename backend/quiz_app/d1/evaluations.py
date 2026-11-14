"""D1-backed evaluation state: the admin's keys and ordered entries, the spend ledger,
and the claims and results on ``attempt_text_marks``.

Two guards make "at most once" and "within the cap" hold under concurrent requests, each
a single conditional statement (D1 runs one statement, and one batch, at a time):

* ``claim_awaiting`` stamps a request's token on an attempt's awaiting rows that nobody
  holds, then reads back only the rows carrying that token. Two submits of one attempt
  can never both send the same answer.
* ``reserve`` inserts the ledger row only if this month's spend of the entry plus the
  reservation stays within the entry's cap (when it has one), and the daily quotas still
  have room. A refused insert writes nothing.

Results are written under the claim: a row whose claim moved on is left alone. Key values
reach this module only sealed (``keycipher``); it never sees a plaintext key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..errors import Conflict, NotFound
from ..models import AWAITING, FLAGGED, MARKED
from ._rows import key_points_from_json


@dataclass(frozen=True)
class StoredBalance:
    limit_micros: int
    spent_micros: int
    currency: str
    source: str

    @property
    def remaining_micros(self) -> int:
        return self.limit_micros - self.spent_micros


@dataclass(frozen=True)
class EvaluatorKey:
    id: int
    provider: str
    label: str
    sealed_key: str
    hint: str
    settings: dict[str, str]
    sealed_billing: str | None
    billing_settings: dict[str, str] | None
    unusable: str | None
    unusable_at: int | None
    checked_at: int | None
    check_result: str | None
    balance: StoredBalance | None
    balance_at: int | None
    balance_error: str | None
    created_at: int


@dataclass(frozen=True)
class EvaluatorEntry:
    id: int
    key_id: int
    provider: str
    key_label: str
    model: str
    position: int
    monthly_cap_micros: int | None
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
    entry_id: int | None
    key_id: int
    provider: str
    model: str
    attempt_id: str | None
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


#: ``update_key``'s billing argument: leave the billing credential as it is.
KEEP = object()

_KEY_COLUMNS = (
    "id, provider, label, sealed_key, hint, settings, sealed_billing, billing_settings, unusable, "
    "unusable_at, checked_at, check_result, balance_limit_micros, balance_spent_micros, "
    "balance_currency, balance_source, balance_at, balance_error, created_at"
)
_ENTRY_COLUMNS = (
    "e.id, e.key_id, k.provider, k.label AS key_label, e.model, e.position, e.monthly_cap_micros, "
    "e.input_price_per_mtok, e.output_price_per_mtok"
)
_ENTRIES = "FROM evaluator_entries e JOIN evaluator_keys k ON k.id = e.key_id"
#: The ledger rows that count toward the daily quotas: marking calls, not probes, and not
#: calls the provider refused with an HTTP error, for credit, for the key or otherwise
#: (nobody was marked or billed). The quotas count the distinct attempts among them, so one
#: attempt is one unit however many entries it tries.
_MARKING = ("trigger <> 'check' AND "
            "(outcome IS NULL OR outcome NOT IN ('out_of_credit', 'key_refused', 'http_error'))")


def _settings(raw: str | None) -> dict[str, str] | None:
    if raw is None:
        return None
    data = json.loads(raw)
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _key(row: dict) -> EvaluatorKey:
    balance = None
    if row["balance_limit_micros"] is not None and row["balance_spent_micros"] is not None:
        balance = StoredBalance(row["balance_limit_micros"], row["balance_spent_micros"],
                                row["balance_currency"] or "USD", row["balance_source"] or "")
    return EvaluatorKey(
        id=row["id"], provider=row["provider"], label=row["label"], sealed_key=row["sealed_key"],
        hint=row["hint"], settings=_settings(row["settings"]) or {}, sealed_billing=row["sealed_billing"],
        billing_settings=_settings(row["billing_settings"]), unusable=row["unusable"],
        unusable_at=row["unusable_at"], checked_at=row["checked_at"], check_result=row["check_result"],
        balance=balance, balance_at=row["balance_at"], balance_error=row["balance_error"],
        created_at=row["created_at"],
    )


def _entry(row: dict) -> EvaluatorEntry:
    return EvaluatorEntry(
        id=row["id"], key_id=row["key_id"], provider=row["provider"], key_label=row["key_label"],
        model=row["model"], position=row["position"], monthly_cap_micros=row["monthly_cap_micros"],
        input_price_per_mtok=row["input_price_per_mtok"], output_price_per_mtok=row["output_price_per_mtok"],
    )


def _placeholders(n: int) -> str:
    return ", ".join("?" for _ in range(n))


def _unique_clash(error: Exception) -> bool:
    return "UNIQUE constraint failed" in str(error)


class D1EvaluationRepository:
    def __init__(self, db):
        self._db = db

    # -- keys ----------------------------------------------------------------

    async def list_keys(self) -> list[EvaluatorKey]:
        rows = (await self._db.prepare(f"SELECT {_KEY_COLUMNS} FROM evaluator_keys ORDER BY id").all()).results
        return [_key(row) for row in rows]

    async def get_key(self, key_id: int) -> EvaluatorKey:
        row = await self._db.prepare(f"SELECT {_KEY_COLUMNS} FROM evaluator_keys WHERE id = ?").bind(key_id).first()
        if row is None:
            raise NotFound("key not found")
        return _key(row)

    async def add_key(
        self, provider: str, label: str, sealed_key: str, hint: str, settings: dict[str, str],
        sealed_billing: str | None, billing_settings: dict[str, str] | None, now: int,
    ) -> int:
        try:
            row = await self._db.prepare(
                "INSERT INTO evaluator_keys (provider, label, sealed_key, hint, settings, sealed_billing, "
                "billing_settings, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id"
            ).bind(
                provider, label, sealed_key, hint, json.dumps(settings), sealed_billing,
                json.dumps(billing_settings) if billing_settings is not None else None, now, now,
            ).first()
        except Exception as e:
            if _unique_clash(e):
                raise Conflict("another key already has that label") from None
            raise
        return row["id"]

    async def update_key(
        self, key_id: int, now: int, label: str | None = None,
        key: tuple[str, str, dict[str, str]] | None = None, billing=KEEP,
    ) -> None:
        """Change the label; replace the key (sealed value, hint, settings), which clears its
        "unusable" mark; and replace (sealed value, settings) or remove (``None``) the billing
        credential, which clears the last reading. Unnamed parts stay as they are."""
        await self.get_key(key_id)
        sets: list[str] = []
        values: list = []
        if label is not None:
            sets.append("label = ?")
            values.append(label)
        if key is not None:
            sealed, hint, settings = key
            sets += ["sealed_key = ?", "hint = ?", "settings = ?", "unusable = NULL", "unusable_at = NULL"]
            values += [sealed, hint, json.dumps(settings)]
        if billing is not KEEP:
            sealed_billing, billing_settings = billing if billing is not None else (None, None)
            sets += ["sealed_billing = ?", "billing_settings = ?", "balance_limit_micros = NULL",
                     "balance_spent_micros = NULL", "balance_currency = NULL", "balance_source = NULL",
                     "balance_at = NULL", "balance_error = NULL"]
            values += [sealed_billing, json.dumps(billing_settings) if billing_settings is not None else None]
        sets.append("updated_at = ?")
        values.append(now)
        try:
            await self._db.prepare(
                f"UPDATE evaluator_keys SET {', '.join(sets)} WHERE id = ?"
            ).bind(*values, key_id).run()
        except Exception as e:
            if _unique_clash(e):
                raise Conflict("another key already has that label") from None
            raise

    async def delete_key(self, key_id: int) -> None:
        """The key and every entry that uses it. Their ledger rows stay."""
        await self.get_key(key_id)
        await self._db.batch([
            self._db.prepare("DELETE FROM evaluator_entries WHERE key_id = ?").bind(key_id),
            self._db.prepare("DELETE FROM evaluator_keys WHERE id = ?").bind(key_id),
        ])

    async def mark_key(self, key_id: int, unusable: str | None, at: int | None) -> None:
        """Mark the key refused for credit or refused outright (``unusable``), or clear the
        mark (``None``)."""
        await self._db.prepare(
            "UPDATE evaluator_keys SET unusable = ?, unusable_at = ? WHERE id = ?"
        ).bind(unusable, at if unusable else None, key_id).run()

    async def record_check(self, key_id: int, at: int, result: str) -> None:
        await self._db.prepare(
            "UPDATE evaluator_keys SET checked_at = ?, check_result = ? WHERE id = ?"
        ).bind(at, result, key_id).run()

    async def record_balance(self, key_id: int, at: int, reading: StoredBalance | None, error: str | None) -> None:
        """Store a reading of the provider's budget, or why it failed (keeping the last good
        reading's figures so the page can still show them, dated)."""
        if reading is None:
            await self._db.prepare(
                "UPDATE evaluator_keys SET balance_error = ? WHERE id = ?"
            ).bind(error, key_id).run()
            return
        await self._db.prepare(
            "UPDATE evaluator_keys SET balance_limit_micros = ?, balance_spent_micros = ?, balance_currency = ?, "
            "balance_source = ?, balance_at = ?, balance_error = NULL WHERE id = ?"
        ).bind(reading.limit_micros, reading.spent_micros, reading.currency, reading.source, at, key_id).run()

    # -- entries -------------------------------------------------------------

    async def list_entries(self) -> list[EvaluatorEntry]:
        rows = (await self._db.prepare(
            f"SELECT {_ENTRY_COLUMNS} {_ENTRIES} ORDER BY e.position, e.id"
        ).all()).results
        return [_entry(row) for row in rows]

    async def get_entry(self, entry_id: int) -> EvaluatorEntry:
        row = await self._db.prepare(f"SELECT {_ENTRY_COLUMNS} {_ENTRIES} WHERE e.id = ?").bind(entry_id).first()
        if row is None:
            raise NotFound("evaluator not found")
        return _entry(row)

    async def add_entry(
        self, key_id: int, model: str, cap_micros: int | None, input_price: float, output_price: float, now: int
    ) -> int:
        await self.get_key(key_id)
        try:
            row = await self._db.prepare(
                "INSERT INTO evaluator_entries (key_id, model, position, monthly_cap_micros, "
                "input_price_per_mtok, output_price_per_mtok, created_at, updated_at) "
                "SELECT ?, ?, COALESCE(MAX(position), -1) + 1, ?, ?, ?, ?, ? FROM evaluator_entries "
                "RETURNING id"
            ).bind(key_id, model, cap_micros, input_price, output_price, now, now).first()
        except Exception as e:
            if _unique_clash(e):
                raise Conflict("that key and model are already in the list") from None
            raise
        return row["id"]

    async def update_entry(
        self, entry_id: int, cap_micros: int | None, input_price: float, output_price: float, now: int
    ) -> None:
        await self.get_entry(entry_id)
        await self._db.prepare(
            "UPDATE evaluator_entries SET monthly_cap_micros = ?, input_price_per_mtok = ?, "
            "output_price_per_mtok = ?, updated_at = ? WHERE id = ?"
        ).bind(cap_micros, input_price, output_price, now, entry_id).run()

    async def delete_entry(self, entry_id: int) -> None:
        await self.get_entry(entry_id)
        await self._db.prepare("DELETE FROM evaluator_entries WHERE id = ?").bind(entry_id).run()

    async def reorder(self, ids: list[int], now: int) -> None:
        await self._db.batch([
            self._db.prepare(
                "UPDATE evaluator_entries SET position = ?, updated_at = ? WHERE id = ?"
            ).bind(position, now, entry_id)
            for position, entry_id in enumerate(ids)
        ])

    # -- the ledger ----------------------------------------------------------

    async def month_spend(self, month: str) -> tuple[dict[int, int], dict[int, int]]:
        """This month's tracked spend in micro-dollars: (by entry, by key). A key's figure
        includes probes of it that no entry took."""
        rows = (await self._db.prepare(
            "SELECT entry_id, key_id, SUM(COALESCE(cost_micros, reserved_micros)) AS spent "
            "FROM evaluation_calls WHERE month = ? GROUP BY entry_id, key_id"
        ).bind(month).all()).results
        by_entry: dict[int, int] = {}
        by_key: dict[int, int] = {}
        for row in rows:
            spent = row["spent"] or 0
            if row["entry_id"] is not None:
                by_entry[row["entry_id"]] = by_entry.get(row["entry_id"], 0) + spent
            by_key[row["key_id"]] = by_key.get(row["key_id"], 0) + spent
        return by_entry, by_key

    async def calls_today(self, day: str, email: str, other_than: str | None = None) -> tuple[int, int]:
        """(attempts evaluated today, this person's attempts evaluated today), leaving out
        the attempt ``other_than`` when given."""
        row = await self._db.prepare(
            "SELECT COUNT(DISTINCT attempt_id) AS everyone, "
            "COUNT(DISTINCT CASE WHEN user_email = ? THEN attempt_id END) AS mine "
            f"FROM evaluation_calls WHERE day = ? AND {_MARKING} AND attempt_id IS NOT ?"
        ).bind(email, day, other_than).first()
        return row["everyone"], row["mine"]

    async def reserve(
        self, r: Reservation, cap_micros: int | None, global_limit: int | None, user_limit: int | None
    ) -> bool:
        """Insert the ledger row only if the entry's cap and the daily quotas allow it (a
        ``None`` cap or limit is not enforced; the quotas count other attempts than this
        one). True when it was inserted."""
        await self._db.prepare(
            "INSERT INTO evaluation_calls (token, entry_id, key_id, provider, model, attempt_id, user_email, "
            "trigger, day, month, reserved_micros, rubric, created_at) "
            "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE "
            "(? IS NULL OR (SELECT COALESCE(SUM(COALESCE(cost_micros, reserved_micros)), 0) FROM evaluation_calls "
            " WHERE entry_id = ? AND month = ?) + ? <= ?) "
            "AND (? IS NULL OR (SELECT COUNT(DISTINCT attempt_id) FROM evaluation_calls "
            f" WHERE day = ? AND {_MARKING} AND attempt_id IS NOT ?) < ?) "
            "AND (? IS NULL OR (SELECT COUNT(DISTINCT attempt_id) FROM evaluation_calls "
            f" WHERE day = ? AND user_email = ? AND {_MARKING} AND attempt_id IS NOT ?) < ?)"
        ).bind(
            r.token, r.entry_id, r.key_id, r.provider, r.model, r.attempt_id, r.user_email, r.trigger,
            r.day, r.month, r.reserved_micros, r.rubric, r.created_at,
            cap_micros, r.entry_id, r.month, r.reserved_micros, cap_micros,
            global_limit, r.day, r.attempt_id, global_limit,
            user_limit, r.day, r.user_email, r.attempt_id, user_limit,
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
