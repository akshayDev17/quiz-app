"""Marking written answers: who evaluates, within what budget, and what is recorded (ADR 0010).

``evaluate(attempt, trigger, quota_exempt)`` is the only path to a model, and it runs only
from a submit (``AttemptService.submit``) or an admin re-run, never from a read. For one
closed attempt it:

1. claims the attempt's awaiting answers (``D1EvaluationRepository.claim_awaiting``), so a
   second request finds nothing to send;
2. packs them into one call (``rubric.pack``); what does not fit waits for the next call,
   and an answer too large to ever fit is flagged;
3. checks the daily quotas (per person and site-wide) when the trigger is a submit;
4. routes: the first entry of the admin's list, in order, whose provider has its secrets
   and whose monthly budget has room for this call's conservative estimate, reserves the
   estimate in the ledger (atomically, with the quotas) and evaluates;
5. settles the ledger to the call's real token cost, logs one line, and records each
   answer as marked (level, award, feedback) or flagged (0, for review).

When nothing can evaluate (no entry, no secret, no budget, quota reached) or the provider
fails, the answers are released still *awaiting*: never scored 0 for a failure of ours.
Only an unusable reply from a model that did answer scores 0, flagged for review. Nothing
is ever retried automatically; an admin re-run picks awaiting answers up later.

Every exception is contained: evaluation can never fail a submit.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from ..clock import Clock
from ..d1.evaluations import (
    D1EvaluationRepository,
    EvaluatorModel,
    Reservation,
    Settlement,
)
from ..errors import Forbidden, Invalid
from ..evaluators import (
    FAKE,
    PROVIDERS,
    REFUSAL,
    TRUNCATED,
    Evaluator,
    EvaluatorReply,
    provider_label,
)
from ..models import Attempt, User
from ..ports import AttemptRepository
from ..rubric import (
    RUBRIC_VERSION,
    EvaluationItem,
    EvaluationRequest,
    award,
    build_request,
    item_key,
    pack,
    parse_reply,
)

SUBMIT, RERUN = "submit", "rerun"

STALE_MS = 10 * 60 * 1000
"""A claim older than this whose request never finished (the Worker was cut off) may be
taken over by an admin re-run. A submit never takes over a claim."""

RERUN_ATTEMPTS = 5
"""Attempts one re-run click evaluates: one model call each, well inside a Worker
request's subrequest and query limits. Click again for more."""

DEFAULT_MONTHLY_BUDGET_USD = 5.0
MAX_MONTHLY_BUDGET_USD = 10_000.0
MAX_PRICE_PER_MTOK = 1_000.0
_MODEL_ID = r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,119}$"

#: Why answers still await evaluation, as recorded for admins (``attempt_text_marks.reason``).
NO_EVALUATOR = "no evaluator configured"
NO_BUDGET = "no budget left"
QUOTA_USER = "daily limit per person reached"
QUOTA_GLOBAL = "daily limit for the site reached"
PROVIDER_ERROR = "provider error"
#: Why an answer was flagged (scored 0) for review.
INVALID_REPLY = "invalid reply"
REFUSED = "model declined"
CUT_OFF = "reply cut off"
TOO_LONG = "too long to evaluate"


@dataclass(frozen=True)
class Quotas:
    """Evaluations (model calls; one per attempt) a submit may trigger per UTC day. Admins are
    exempt from the per-person limit, and admin re-runs from both."""

    user_daily: int = 20
    global_daily: int = 300


@dataclass(frozen=True)
class PricePreset:
    provider: str
    model: str
    input_per_mtok: float
    output_per_mtok: float
    source: str


_ANTHROPIC_SOURCE = (
    "Anthropic list price, platform.claude.com/docs/en/about-claude/pricing, read 2026-11-13 "
    "(Claude Haiku 5.5: prompts up to 100k tokens)."
)
_FOUNDRY_SOURCE = (
    "Claude in Microsoft Foundry bills Anthropic's standard per-model rates in Claude Consumption "
    "Units at $0.01 each (platform.claude.com pricing, 'Claude in Microsoft Foundry pricing', read "
    "2026-11-13). Global Standard deployments; US Data Zone deployments cost 1.1x."
)
_BEDROCK_SOURCE = (
    "Not verified: aws.amazon.com/bedrock/pricing showed no rows for these models in its page text "
    "on 2026-11-13. Prefilled with Anthropic's list rates; Bedrock regional endpoints cost 10% more "
    "than global ones (platform.claude.com pricing, read 2026-11-13). Check the AWS page."
)

PRICE_PRESETS: tuple[PricePreset, ...] = tuple(
    PricePreset(provider, prefix + model, inp, out, source)
    for provider, prefix, source in (
        ("anthropic", "", _ANTHROPIC_SOURCE),
        ("bedrock", "anthropic.", _BEDROCK_SOURCE),
        ("azure", "", _FOUNDRY_SOURCE),
    )
    for model, inp, out in (
        ("claude-haiku-5-5", 0.10, 0.50),
        ("claude-sonnet-5-5", 2.0, 10.0),
        ("claude-opus-5-5", 4.0, 20.0),
    )
)
FAKE_PRESET = PricePreset(FAKE, "fake-overlap", 0.0, 0.0, "Local stand-in; costs nothing.")


@dataclass(frozen=True)
class ProviderStatus:
    id: str
    label: str
    secrets: tuple[str, ...]   # names only, never values
    usable: bool


@dataclass(frozen=True)
class EntryStatus:
    entry: EvaluatorModel
    label: str
    spent_micros: int
    usable: bool

    @property
    def remaining_micros(self) -> int:
        return max(0, self.entry.monthly_budget_micros - self.spent_micros)


@dataclass(frozen=True)
class EvaluatorsOverview:
    providers: tuple[ProviderStatus, ...]
    entries: tuple[EntryStatus, ...]
    presets: tuple[PricePreset, ...]
    month: str
    awaiting: int
    flagged: int
    awaiting_reasons: dict[str, int]
    quotas: Quotas
    calls_today: int


def utc_day(now_ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now_ms // 1000))


def utc_month(now_ms: int) -> str:
    return time.strftime("%Y-%m", time.gmtime(now_ms // 1000))


def estimate_micros(entry: EvaluatorModel, request: EvaluationRequest) -> int:
    """A ceiling on one call's cost: input tokens taken as one per two characters (English
    runs nearer one per four) and the full ``max_tokens`` of output."""
    input_tokens = math.ceil((len(request.system) + len(request.user)) / 2)
    return math.ceil(input_tokens * entry.input_price_per_mtok
                     + request.max_output_tokens * entry.output_price_per_mtok)


def cost_micros(entry: EvaluatorModel, input_tokens: int, output_tokens: int) -> int:
    """Micro-dollars: a price per million tokens is micro-dollars per token."""
    return math.ceil(input_tokens * entry.input_price_per_mtok + output_tokens * entry.output_price_per_mtok)


def _require_admin(user: User) -> None:
    if not user.can_edit_sets:
        raise Forbidden("admin only")


class EvaluationService:
    def __init__(
        self,
        repo: D1EvaluationRepository,
        attempts: AttemptRepository,
        evaluators: dict[str, Evaluator],
        clock: Clock,
        quotas: Quotas | None = None,
        log: Callable[[str], None] = print,
        nonce: Callable[[], str] = lambda: secrets.token_hex(8),
    ):
        self._repo = repo
        self._attempts = attempts
        self._evaluators = dict(evaluators)
        self._clock = clock
        self._quotas = quotas or Quotas()
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

        global_limit = None if trigger == RERUN else self._quotas.global_daily
        user_limit = None if trigger == RERUN or quota_exempt else self._quotas.user_daily
        day, month = utc_day(now), utc_month(now)
        quota = await self._quota_reason(day, attempt.user_email, global_limit, user_limit)
        if quota:
            await self._repo.release(attempt.id, token, waiting, quota)
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return

        chosen = await self._route(attempt, request, token, trigger, day, month, now, global_limit, user_limit)
        if isinstance(chosen, str):
            await self._repo.release(attempt.id, token, waiting, chosen)
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return
        entry, evaluator, reserved = chosen

        try:
            reply = await evaluator.evaluate(request, entry.model)
        except Exception:  # an adapter must not raise; if one does, treat it as no answer
            reply = EvaluatorReply("error", usage_unknown=True)
        cost = reserved if reply.usage_unknown else cost_micros(entry, reply.input_tokens, reply.output_tokens)
        await self._repo.settle(token, Settlement(
            cost_micros=cost, input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
            latency_ms=reply.latency_ms, http_status=reply.http_status, request_id=reply.request_id,
            outcome=reply.outcome,
        ))
        # Only status, request id, provider, model, token counts, latency and cost: never the
        # prompt, an answer, a header, an error body or anyone's email.
        self._log(json.dumps({
            "event": "evaluation_call", "provider": entry.provider, "model": entry.model,
            "outcome": reply.outcome, "status": reply.http_status, "request_id": reply.request_id,
            "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
            "latency_ms": reply.latency_ms, "cost_micros": cost, "items": len(keyed),
        }))

        if not reply.answered:
            await self._repo.release(attempt.id, token, waiting, PROVIDER_ERROR)
            await self._repo.record(attempt.id, token, [], flagged, None, None, now)
            return
        if reply.outcome in (REFUSAL, TRUNCATED):
            reason = REFUSED if reply.outcome == REFUSAL else CUT_OFF
            flagged += [(qid, reason) for qid in waiting]
            await self._repo.record(attempt.id, token, [], flagged, entry.provider, entry.model, now)
            return
        verdicts = parse_reply(reply.text, list(question_of))
        max_marks = attempt.subjective_marks
        marked = []
        for key, qid in question_of.items():
            verdict = verdicts.get(key)
            if verdict is None:
                flagged.append((qid, INVALID_REPLY))
            else:
                marked.append((qid, verdict.level, award(verdict.level, max_marks), verdict.feedback))
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

    async def _route(self, attempt, request, token, trigger, day, month, now, global_limit, user_limit):
        """(entry, evaluator, reserved micro-dollars) for the first entry that can take this
        call, or the reason none could."""
        reason = NO_EVALUATOR
        spend = await self._repo.month_spend(month)
        for entry in await self._repo.list_models():
            evaluator = self._evaluators.get(entry.provider)
            if evaluator is None:
                continue
            reserved = estimate_micros(entry, request)
            if spend.get((entry.provider, entry.model), 0) + reserved > entry.monthly_budget_micros:
                reason = NO_BUDGET
                continue
            ok = await self._repo.reserve(
                Reservation(
                    token=token, provider=entry.provider, model=entry.model, attempt_id=attempt.id,
                    user_email=attempt.user_email, trigger=trigger, day=day, month=month,
                    reserved_micros=reserved, rubric=RUBRIC_VERSION, created_at=now,
                ),
                entry.monthly_budget_micros, global_limit, user_limit,
            )
            if ok:
                return entry, evaluator, reserved
            # Refused: a concurrent call took the last of the budget or of a quota.
            quota = await self._quota_reason(day, attempt.user_email, global_limit, user_limit)
            if quota:
                return quota
            reason = NO_BUDGET
        return reason

    async def rerun(self, user: User) -> tuple[int, int]:
        """Evaluate up to ``RERUN_ATTEMPTS`` attempts with awaiting answers, oldest first,
        exempt from the daily quotas (never from budgets). Returns (attempts tried, still
        awaiting answers)."""
        _require_admin(user)
        now = self._clock.now_ms()
        ids = await self._repo.attempts_awaiting(RERUN_ATTEMPTS, now - STALE_MS)
        for attempt_id in ids:
            attempt = await self._attempts.get(attempt_id)
            if attempt is not None:
                await self.evaluate(attempt, RERUN, quota_exempt=True)
        awaiting, _, _ = await self._repo.queue()
        return len(ids), awaiting

    # -- the admin's list ----------------------------------------------------

    def _known_providers(self) -> list[ProviderStatus]:
        statuses = [ProviderStatus(s.id, s.label, s.secrets, s.id in self._evaluators) for s in PROVIDERS.values()]
        if FAKE in self._evaluators:
            statuses.append(ProviderStatus(FAKE, provider_label(FAKE), (), True))
        return statuses

    async def overview(self, user: User) -> EvaluatorsOverview:
        _require_admin(user)
        now = self._clock.now_ms()
        month = utc_month(now)
        spend = await self._repo.month_spend(month)
        entries = tuple(
            EntryStatus(
                entry=e, label=provider_label(e.provider),
                spent_micros=spend.get((e.provider, e.model), 0),
                usable=e.provider in self._evaluators,
            )
            for e in await self._repo.list_models()
        )
        awaiting, flagged, reasons = await self._repo.queue()
        everyone, _ = await self._repo.calls_today(utc_day(now), user.email)
        presets = PRICE_PRESETS + ((FAKE_PRESET,) if FAKE in self._evaluators else ())
        return EvaluatorsOverview(
            providers=tuple(self._known_providers()), entries=entries, presets=presets, month=month,
            awaiting=awaiting, flagged=flagged, awaiting_reasons=reasons, quotas=self._quotas,
            calls_today=everyone,
        )

    async def add(self, user: User, payload: object) -> None:
        _require_admin(user)
        body = payload if isinstance(payload, dict) else {}
        provider = body.get("provider")
        known = {p.id for p in self._known_providers()}
        errors: list[str] = []
        if provider not in known:
            errors.append(f"provider must be one of {', '.join(sorted(known))}")
        model = body.get("model")
        if not isinstance(model, str) or not re.match(_MODEL_ID, model.strip()):
            errors.append("model must be a model id (letters, digits and . _ : / @ -), at most 120 characters")
        budget, input_price, output_price = _money_fields(body, errors)
        if errors:
            raise Invalid("; ".join(errors))
        await self._repo.add_model(provider, model.strip(), budget, input_price, output_price, self._clock.now_ms())

    async def update(self, user: User, model_id: int, payload: object) -> None:
        _require_admin(user)
        errors: list[str] = []
        budget, input_price, output_price = _money_fields(payload if isinstance(payload, dict) else {}, errors)
        if errors:
            raise Invalid("; ".join(errors))
        await self._repo.update_model(model_id, budget, input_price, output_price, self._clock.now_ms())

    async def remove(self, user: User, model_id: int) -> None:
        _require_admin(user)
        await self._repo.delete_model(model_id)

    async def reorder(self, user: User, payload: object) -> None:
        """``{"ids": [...]}``: every entry's id exactly once, first to last."""
        _require_admin(user)
        ids = payload.get("ids") if isinstance(payload, dict) else None
        current = [e.id for e in await self._repo.list_models()]
        if (not isinstance(ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in ids)
                or sorted(ids) != sorted(current)):
            raise Invalid("ids must list every evaluator exactly once")
        await self._repo.reorder(ids, self._clock.now_ms())


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _money_fields(body: dict, errors: list[str]) -> tuple[int, float, float]:
    """(budget in micro-dollars, input price, output price) from a payload in USD."""
    budget = _number(body.get("monthly_budget_usd"))
    if budget is None or not 0 <= budget <= MAX_MONTHLY_BUDGET_USD:
        errors.append(f"monthly_budget_usd must be a number from 0 to {MAX_MONTHLY_BUDGET_USD:,.0f}")
        budget = 0.0
    prices = []
    for key in ("input_price_per_mtok", "output_price_per_mtok"):
        price = _number(body.get(key))
        if price is None or not 0 <= price <= MAX_PRICE_PER_MTOK:
            errors.append(f"{key} must be a number of USD per million tokens, from 0 to {MAX_PRICE_PER_MTOK:,.0f}")
            price = 0.0
        prices.append(price)
    return round(budget * 1_000_000), prices[0], prices[1]
