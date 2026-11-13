"""Marking written answers: who evaluates, within what limits, and what is recorded
(ADR 0010; keys and money: ADR 0011).

``evaluate(attempt, trigger, quota_exempt)`` is the only path to a model, and it runs only
from a submit (``AttemptService.submit``) or an admin re-run, never from a read. For one
closed attempt it:

1. claims the attempt's awaiting answers (``D1EvaluationRepository.claim_awaiting``), so a
   second request finds nothing to send;
2. packs them into one call (``rubric.pack``); what does not fit waits for the next call,
   and an answer too large to ever fit is flagged;
3. checks the daily quotas (per person and site-wide) when the trigger is a submit;
4. routes down the admin's ordered list of entries (a key and a model each): an entry is
   skipped while its key is marked out of credit or refused (until a retry is due), when
   its key cannot be opened, or when its optional monthly cap has no room for this call's
   conservative estimate. The first entry that can take the call reserves the estimate in
   the ledger (atomically, with the cap and the quotas) and is called. A credit refusal
   or a refused key marks the key and moves on to the next entry; so does any other
   failure (an HTTP error, a timeout, a reply cut off at ``max_tokens``), without marking
   the key. A reply the model finished ends the walk;
5. settles the ledger to the call's real token cost, logs one line, and records each
   answer as marked (level, award, feedback) or flagged (0, for review).

When nothing can evaluate or every entry fails, the answers are released still
*awaiting*, with the last failure's reason: never scored 0 for a failure of ours. Only a
finished reply that is unusable (a refusal, or no valid verdict) scores 0, flagged for
review. Answers are never re-sent automatically; an admin re-run picks awaiting answers
up later.

Every exception is contained: evaluation can never fail a submit.
"""

from __future__ import annotations

import json
import math
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from uuid import uuid4

from ..clock import Clock
from ..d1.evaluations import D1EvaluationRepository, EvaluatorEntry, EvaluatorKey, Reservation, Settlement
from ..errors import Forbidden
from ..evaluators import KEY_REFUSED, OUT_OF_CREDIT, REFUSAL, TRUNCATED, Evaluator, EvaluatorReply
from ..models import Attempt, User
from ..ports import AttemptRepository
from ..rubric import (
    RUBRIC_VERSION,
    EvaluationItem,
    EvaluationRequest,
    award,
    build_request,
    hide_answer_terms,
    item_key,
    pack,
    parse_reply,
)
from .keyring import KeyRing

SUBMIT, RERUN, CHECK = "submit", "rerun", "check"

STALE_MS = 10 * 60 * 1000
"""A claim older than this whose request never finished (the Worker was cut off) may be
taken over by an admin re-run. A submit never takes over a claim."""

RETRY_UNUSABLE_MS = 60 * 60 * 1000
"""A key marked out of credit or refused is skipped for this long, then tried again by
the next marking call; a "check now" tries it at once."""

RERUN_ATTEMPTS = 5
"""Attempts one re-run click evaluates: one model call each (plus one per entry that
fails and passes the call down the list), well inside a Worker request's subrequest and query limits."""

#: Why answers still await evaluation, as recorded for admins (``attempt_text_marks.reason``).
NO_EVALUATOR = "no evaluator configured"
CAP_REACHED = "monthly cap reached"
OUT_OF_CREDIT_REASON = "out of credit at provider"
KEY_REFUSED_REASON = "key refused by provider"
QUOTA_USER = "daily limit per person reached"
QUOTA_GLOBAL = "daily limit for the site reached"
PROVIDER_ERROR = "provider error"
CUT_OFF = "reply cut off"
#: Why an answer was flagged (scored 0) for review.
INVALID_REPLY = "invalid reply"
REFUSED = "model declined"
TOO_LONG = "too long to evaluate"

UNUSABLE_REASONS = {OUT_OF_CREDIT: OUT_OF_CREDIT_REASON, KEY_REFUSED: KEY_REFUSED_REASON}


@dataclass(frozen=True)
class EvaluationSettings:
    """The numbers the owner has not settled yet, kept as configuration (``settings_from``)
    with these defaults: daily evaluations (model calls; one per attempt) a submit may
    trigger, per person and site-wide (admins are exempt from the per-person limit, admin
    re-runs from both); and the cap prefilled for a new entry."""

    user_daily: int = 20
    global_daily: int = 300
    default_cap_usd: float = 5.0


def utc_day(now_ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now_ms // 1000))


def utc_month(now_ms: int) -> str:
    return time.strftime("%Y-%m", time.gmtime(now_ms // 1000))


def estimate_micros(entry: EvaluatorEntry, request: EvaluationRequest) -> int:
    """A ceiling on one call's cost: input tokens taken as one per two characters (English
    runs nearer one per four) and the full ``max_tokens`` of output."""
    input_tokens = math.ceil((len(request.system) + len(request.user)) / 2)
    return math.ceil(input_tokens * entry.input_price_per_mtok
                     + request.max_output_tokens * entry.output_price_per_mtok)


def cost_micros(entry: EvaluatorEntry, input_tokens: int, output_tokens: int) -> int:
    """Micro-dollars: a price per million tokens is micro-dollars per token."""
    return math.ceil(input_tokens * entry.input_price_per_mtok + output_tokens * entry.output_price_per_mtok)


def unusable_now(key: EvaluatorKey, now: int) -> bool:
    """Is the key marked out of credit or refused, and not yet due a retry?"""
    return bool(key.unusable) and key.unusable_at is not None and now < key.unusable_at + RETRY_UNUSABLE_MS


def require_admin(user: User) -> None:
    if not user.can_edit_sets:
        raise Forbidden("admin only")


class EvaluationService:
    def __init__(
        self,
        repo: D1EvaluationRepository,
        attempts: AttemptRepository,
        ring: KeyRing,
        clock: Clock,
        settings: EvaluationSettings | None = None,
        log: Callable[[str], None] = print,
        nonce: Callable[[], str] = lambda: secrets.token_hex(8),
    ):
        self._repo = repo
        self._attempts = attempts
        self._ring = ring
        self._clock = clock
        self._settings = settings or EvaluationSettings()
        self._log = log
        self._nonce = nonce

    # -- marking -------------------------------------------------------------

    async def evaluate(self, attempt: Attempt, trigger: str, quota_exempt: bool = False) -> None:
        """Mark what the attempt still has awaiting. Never raises."""
        try:
            await self._evaluate(attempt, trigger, quota_exempt)
        except Exception as e:  # contained: a submit must succeed whatever happens here
            self._log(json.dumps({"event": "evaluation_error", "error_class": type(e).__name__}))

    async def _evaluate(self, attempt: Attempt, trigger: str, quota_exempt: bool) -> None:
        if attempt.subjective_marks is None or attempt.is_open:
            return
        now = self._clock.now_ms()
        token = uuid4().hex
        claimed = await self._repo.claim_awaiting(
            attempt.id, token, now, now - STALE_MS if trigger == RERUN else None
        )
        if not claimed:
            return
        first = [EvaluationItem(str(c.question_id), c.prompt, c.model_answer, c.key_points, c.text)
                 for c in claimed]
        now_items, later, never = pack(first)
        flagged = [(int(item.key), TOO_LONG) for item in never]
        await self._repo.release(attempt.id, token, [int(item.key) for item in later], None)
        if not now_items:
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return

        # Re-key in call order: the model sees Q1, Q2…, never a database id.
        keyed = [EvaluationItem(item_key(i), it.question, it.model_answer, it.key_points, it.answer)
                 for i, it in enumerate(now_items)]
        question_of = {k.key: int(it.key) for k, it in zip(keyed, now_items)}
        request = build_request(keyed, attempt.reveal_answers, self._nonce())
        waiting = list(question_of.values())

        global_limit = None if trigger == RERUN else self._settings.global_daily
        user_limit = None if trigger == RERUN or quota_exempt else self._settings.user_daily
        day, month = utc_day(now), utc_month(now)
        quota = await self._quota_reason(day, attempt.user_email, global_limit, user_limit)
        if quota:
            await self._repo.release(attempt.id, token, waiting, quota)
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return

        outcome = await self._route_and_call(attempt, request, trigger, day, month, now, global_limit, user_limit)
        if isinstance(outcome, str):
            await self._repo.release(attempt.id, token, waiting, outcome)
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return
        entry, reply = outcome

        if reply.outcome == REFUSAL:
            flagged += [(qid, REFUSED) for qid in waiting]
            await self._repo.record(attempt.id, token, [], flagged, entry.provider, entry.model, now)
            return
        verdicts = parse_reply(reply.text, list(question_of))
        max_marks = attempt.subjective_marks
        item_of = {it.key: it for it in keyed}
        marked = []
        for key, qid in question_of.items():
            verdict = verdicts.get(key)
            if verdict is None:
                flagged.append((qid, INVALID_REPLY))
                continue
            feedback = verdict.feedback
            if not attempt.reveal_answers:
                feedback = hide_answer_terms(feedback, item_of[key], verdict.level)
            marked.append((qid, verdict.level, award(verdict.level, max_marks), feedback))
        await self._repo.record(attempt.id, token, marked, flagged, entry.provider, entry.model, now)

    async def _quota_reason(self, day: str, email: str, global_limit: int | None, user_limit: int | None) -> str | None:
        if global_limit is None and user_limit is None:
            return None
        everyone, mine = await self._repo.calls_today(day, email)
        if global_limit is not None and everyone >= global_limit:
            return QUOTA_GLOBAL
        if user_limit is not None and mine >= user_limit:
            return QUOTA_USER
        return None

    async def _route_and_call(self, attempt, request, trigger, day, month, now, global_limit, user_limit):
        """(entry, reply) of the first call the model finished, or why no entry could take
        the call (the last failure's reason)."""
        entries = await self._repo.list_entries()
        if not entries:
            return NO_EVALUATOR
        keys = {k.id: k for k in await self._repo.list_keys()}
        spend, _ = await self._repo.month_spend(month)
        opened: dict[int, Evaluator | str] = {}
        reason = NO_EVALUATOR
        for entry in entries:
            key = keys.get(entry.key_id)
            if key is None:
                continue
            if unusable_now(key, now):
                reason = UNUSABLE_REASONS[key.unusable]
                continue
            if key.id not in opened:
                opened[key.id] = await self._ring.evaluator(key)
            evaluator = opened[key.id]
            if isinstance(evaluator, str):
                reason = evaluator
                continue
            reserved = estimate_micros(entry, request)
            cap = entry.monthly_cap_micros
            if cap is not None and spend.get(entry.id, 0) + reserved > cap:
                reason = CAP_REACHED
                continue
            call = uuid4().hex
            ok = await self._repo.reserve(
                Reservation(
                    token=call, entry_id=entry.id, key_id=key.id, provider=entry.provider, model=entry.model,
                    attempt_id=attempt.id, user_email=attempt.user_email, trigger=trigger, day=day,
                    month=month, reserved_micros=reserved, rubric=RUBRIC_VERSION, created_at=now,
                ),
                cap, global_limit, user_limit,
            )
            if not ok:  # a concurrent call took the last of the cap or of a quota
                quota = await self._quota_reason(day, attempt.user_email, global_limit, user_limit)
                if quota:
                    return quota
                reason = CAP_REACHED
                continue
            reply = await self._call(evaluator, request, entry, call, reserved, len(request.items))
            if reply.outcome in UNUSABLE_REASONS:
                await self._repo.mark_key(key.id, reply.outcome, now)
                keys[key.id] = replace(key, unusable=reply.outcome, unusable_at=now)
                reason = UNUSABLE_REASONS[reply.outcome]
                continue
            if key.unusable and reply.answered:  # the retry worked: the key has credit again
                await self._repo.mark_key(key.id, None, None)
                keys[key.id] = replace(key, unusable=None, unusable_at=None)
            if not reply.answered:
                reason = PROVIDER_ERROR
                continue
            if reply.outcome == TRUNCATED:
                reason = CUT_OFF
                continue
            return entry, reply
        return reason

    async def _call(self, evaluator: Evaluator, request: EvaluationRequest, entry: EvaluatorEntry,
                    call: str, reserved: int, items: int) -> EvaluatorReply:
        try:
            reply = await evaluator.evaluate(request, entry.model)
        except Exception:  # an adapter must not raise; if one does, treat it as no answer
            reply = EvaluatorReply("error", usage_unknown=True)
        cost = reserved if reply.usage_unknown else cost_micros(entry, reply.input_tokens, reply.output_tokens)
        await self._repo.settle(call, Settlement(
            cost_micros=cost, input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
            latency_ms=reply.latency_ms, http_status=reply.http_status, request_id=reply.request_id,
            outcome=reply.outcome,
        ))
        # Only status, request id, provider, model, token counts, latency and cost: never the
        # prompt, an answer, a header, a key, an error body or anyone's email.
        self._log(json.dumps({
            "event": "evaluation_call", "provider": entry.provider, "model": entry.model,
            "outcome": reply.outcome, "status": reply.http_status, "request_id": reply.request_id,
            "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
            "latency_ms": reply.latency_ms, "cost_micros": cost, "items": items,
        }))
        return reply

    async def rerun(self, user: User) -> tuple[int, int]:
        """Evaluate up to ``RERUN_ATTEMPTS`` attempts with awaiting answers, oldest first,
        exempt from the daily quotas (never from caps). Returns (attempts tried, still
        awaiting answers)."""
        require_admin(user)
        now = self._clock.now_ms()
        ids = await self._repo.attempts_awaiting(RERUN_ATTEMPTS, now - STALE_MS)
        for attempt_id in ids:
            attempt = await self._attempts.get(attempt_id)
            if attempt is not None:
                await self.evaluate(attempt, RERUN, quota_exempt=True)
        awaiting, _, _ = await self._repo.queue()
        return len(ids), awaiting
