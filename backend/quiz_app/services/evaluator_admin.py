"""The admin's evaluator page: keys, the ordered list of entries, and what each can spend
(ADR 0011). Every method is admin-only, checked here on every call.

* Keys are first-class: add (the values are sealed at once), replace (the key, its label,
  or its billing credential), remove (with every entry that uses it). A key is never
  shown back: the page gets its provider, label, last four characters, non-secret
  settings, and status.
* Entries are a key and a model, in the admin's order, each with prices for the app's
  spend tracking and an optional monthly cap.
* "Check now" probes a key with the smallest billable request, to see whether the
  provider still takes it (it clears or sets the out-of-credit mark), and, where the
  provider can report one, reads the real budget figure with the read-only billing
  credential.

Money shown is what the provider reports where it can (a cloud budget), else the app's
own tracking of each call's tokens times the entry's prices, never a typed-in balance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from uuid import uuid4

from ..billing import BillingError
from ..clock import Clock
from ..d1.evaluations import (
    KEEP,
    D1EvaluationRepository,
    EvaluatorEntry,
    EvaluatorKey,
    Reservation,
    Settlement,
    StoredBalance,
)
from ..errors import Conflict, Invalid
from ..evaluators import FAKE, KEY_REFUSED, OUT_OF_CREDIT, ProviderSpec, key_hint
from ..models import User
from ..rubric import RUBRIC_VERSION
from .evaluation import (
    CHECK,
    RETRY_UNUSABLE_MS,
    UNUSABLE_REASONS,
    EvaluationSettings,
    cost_micros,
    require_admin,
    utc_day,
    utc_month,
)
from .keyring import NO_KEY_STORAGE, KeyRing, read_fields

MAX_CAP_USD = 10_000.0
MAX_PRICE_PER_MTOK = 1_000.0
_MODEL_ID = r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,119}$"
_LABEL_MAX = 60
#: A probe's reservation: its prompt is a few words, its reply at most 16 tokens.
_PROBE_INPUT_TOKENS, _PROBE_OUTPUT_TOKENS = 64, 16

#: What "check now" found, as stored and shown.
CHECK_WORKING = "working"
CHECK_NEEDS_ENTRY = "add an entry for this key first: the check needs its deployment or model name"


@dataclass(frozen=True)
class PricePreset:
    provider: str
    model: str
    input_per_mtok: float
    output_per_mtok: float
    source: str


_ANTHROPIC_SOURCE = "Anthropic list price, platform.claude.com/docs/en/about-claude/pricing, read 2026-11-13."
#: Only Haiku 5.5 is priced by prompt size: its rates hold up to 100k tokens ($0.50 / $2.50 above).
_HAIKU_SOURCE = (
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

PRICE_PRESETS: tuple[PricePreset, ...] = (
    PricePreset("anthropic", "claude-haiku-5-5", 0.10, 0.50, _HAIKU_SOURCE),
    PricePreset("anthropic", "claude-sonnet-5-5", 2.0, 10.0, _ANTHROPIC_SOURCE),
    PricePreset("anthropic", "claude-opus-5-5", 4.0, 20.0, _ANTHROPIC_SOURCE),
    PricePreset("bedrock", "anthropic.claude-haiku-5-5", 0.10, 0.50, _BEDROCK_SOURCE),
    PricePreset("bedrock", "anthropic.claude-sonnet-5-5", 2.0, 10.0, _BEDROCK_SOURCE),
    PricePreset("bedrock", "anthropic.claude-opus-5-5", 4.0, 20.0, _BEDROCK_SOURCE),
    PricePreset("azure", "claude-haiku-5-5", 0.10, 0.50, _FOUNDRY_SOURCE),
    PricePreset("azure", "claude-sonnet-5-5", 2.0, 10.0, _FOUNDRY_SOURCE),
    PricePreset("azure", "claude-opus-5-5", 4.0, 20.0, _FOUNDRY_SOURCE),
)
FAKE_PRESET = PricePreset(FAKE, "fake-overlap", 0.0, 0.0, "Local stand-in; costs nothing.")

#: A key's state on the page.
READY, UNREADABLE = "ready", "unreadable"


@dataclass(frozen=True)
class KeyStatus:
    key: EvaluatorKey
    provider_label: str
    state: str                 # READY, OUT_OF_CREDIT, KEY_REFUSED or UNREADABLE
    problem: str | None        # why it cannot be used now, in words
    retry_at: int | None       # when marking will try an out-of-credit or refused key again
    spent_micros: int          # this month, every entry of the key plus its probes
    entries: int
    reads_balance: bool


@dataclass(frozen=True)
class EntryStatus:
    entry: EvaluatorEntry
    provider_label: str
    spent_micros: int
    usable: bool
    problem: str | None
    balance: StoredBalance | None
    balance_at: int | None

    @property
    def left_of_cap_micros(self) -> int | None:
        cap = self.entry.monthly_cap_micros
        return None if cap is None else max(0, cap - self.spent_micros)


@dataclass(frozen=True)
class EvaluatorsOverview:
    key_storage_ready: bool
    providers: tuple[ProviderSpec, ...]
    keys: tuple[KeyStatus, ...]
    entries: tuple[EntryStatus, ...]
    presets: tuple[PricePreset, ...]
    month: str
    awaiting: int
    flagged: int
    awaiting_reasons: dict[str, int]
    settings: EvaluationSettings
    calls_today: int


@dataclass(frozen=True)
class CheckResult:
    result: str
    balance_error: str | None


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _label(raw: object, errors: list[str]) -> str:
    label = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not 1 <= len(label) <= _LABEL_MAX:
        errors.append(f"label must be 1 to {_LABEL_MAX} characters")
    return label


def _entry_money(body: dict, errors: list[str]) -> tuple[int | None, float, float]:
    """(cap in micro-dollars or None, input price, output price) from a payload in USD."""
    raw_cap = body.get("monthly_cap_usd")
    cap = None
    if raw_cap is not None:
        value = _number(raw_cap)
        if value is None or not 0 <= value <= MAX_CAP_USD:
            errors.append(f"monthly_cap_usd must be empty (no cap) or a number from 0 to {MAX_CAP_USD:,.0f}")
        else:
            cap = round(value * 1_000_000)
    prices = []
    for key in ("input_price_per_mtok", "output_price_per_mtok"):
        price = _number(body.get(key))
        if price is None or not 0 <= price <= MAX_PRICE_PER_MTOK:
            errors.append(f"{key} must be a number of USD per million tokens, from 0 to {MAX_PRICE_PER_MTOK:,.0f}")
            price = 0.0
        prices.append(price)
    return cap, prices[0], prices[1]


class EvaluatorAdmin:
    def __init__(self, repo: D1EvaluationRepository, ring: KeyRing, clock: Clock,
                 settings: EvaluationSettings | None = None):
        self._repo = repo
        self._ring = ring
        self._clock = clock
        self._settings = settings or EvaluationSettings()

    # -- the page ------------------------------------------------------------

    async def overview(self, user: User) -> EvaluatorsOverview:
        require_admin(user)
        now = self._clock.now_ms()
        month = utc_month(now)
        by_entry, by_key = await self._repo.month_spend(month)
        entries = await self._repo.list_entries()
        keys: list[KeyStatus] = []
        for key in await self._repo.list_keys():
            spec = self._ring.providers.get(key.provider)
            opened = await self._ring.evaluator(key)
            if isinstance(opened, str):
                state, problem = UNREADABLE, opened
            elif key.unusable:
                state, problem = key.unusable, UNUSABLE_REASONS[key.unusable]
            else:
                state, problem = READY, None
            keys.append(KeyStatus(
                key=key, provider_label=spec.label if spec else key.provider, state=state, problem=problem,
                retry_at=(key.unusable_at + RETRY_UNUSABLE_MS) if key.unusable and key.unusable_at else None,
                spent_micros=by_key.get(key.id, 0), entries=sum(1 for e in entries if e.key_id == key.id),
                reads_balance=self._ring.reads_balance(key),
            ))
        status_of = {k.key.id: k for k in keys}
        rows = []
        for e in entries:
            k = status_of[e.key_id]
            spent = by_entry.get(e.id, 0)
            problem = k.problem
            if problem is None and e.monthly_cap_micros is not None and spent >= e.monthly_cap_micros:
                problem = "monthly cap reached"
            rows.append(EntryStatus(
                entry=e, provider_label=k.provider_label, spent_micros=spent, usable=problem is None,
                problem=problem, balance=k.key.balance, balance_at=k.key.balance_at,
            ))
        awaiting, flagged, reasons = await self._repo.queue()
        everyone, _ = await self._repo.calls_today(utc_day(now), user.email)
        presets = PRICE_PRESETS + ((FAKE_PRESET,) if FAKE in self._ring.providers else ())
        return EvaluatorsOverview(
            key_storage_ready=self._ring.ready, providers=tuple(self._ring.providers.values()),
            keys=tuple(keys), entries=tuple(rows), presets=presets, month=month, awaiting=awaiting,
            flagged=flagged, awaiting_reasons=reasons, settings=self._settings, calls_today=everyone,
        )

    # -- keys ----------------------------------------------------------------

    async def add_key(self, user: User, payload: object) -> int:
        """``{provider, label, fields: {...}, billing: {...} | null}``."""
        require_admin(user)
        body = payload if isinstance(payload, dict) else {}
        spec = self._ring.spec(body.get("provider"))
        errors: list[str] = []
        label = _label(body.get("label"), errors)
        secrets, plain = read_fields(spec.key_fields, body.get("fields"), "key", errors)
        billing = self._billing_from(spec, body.get("billing"), errors)
        if errors:
            raise Invalid("; ".join(errors))
        if not self._ring.ready:
            raise_no_storage()
        sealed = await self._ring.seal_key(spec.id, secrets)
        sealed_billing, billing_settings = (await self._seal_billing(spec, billing)) if billing else (None, None)
        return await self._repo.add_key(spec.id, label, sealed, key_hint(secrets), plain, sealed_billing,
                                        billing_settings, self._clock.now_ms())

    async def update_key(self, user: User, key_id: int, payload: object) -> None:
        """Any of ``label``; ``fields`` (the whole key, re-entered); ``billing`` (the whole
        billing credential, or ``null`` to remove it). Absent parts stay as they are."""
        require_admin(user)
        key = await self._repo.get_key(key_id)
        spec = self._ring.spec(key.provider)
        body = payload if isinstance(payload, dict) else {}
        errors: list[str] = []
        label = _label(body["label"], errors) if "label" in body else None
        fields = read_fields(spec.key_fields, body["fields"], "key", errors) if "fields" in body else None
        billing = self._billing_from(spec, body["billing"], errors) if "billing" in body else KEEP
        if not ({"label", "fields", "billing"} & set(body)):
            errors.append("send a label, the key's fields, or its billing credential")
        if errors:
            raise Invalid("; ".join(errors))
        if (fields is not None or billing not in (KEEP, None)) and not self._ring.ready:
            raise_no_storage()
        sealed_key = None
        if fields is not None:
            secrets, plain = fields
            sealed_key = (await self._ring.seal_key(spec.id, secrets), key_hint(secrets), plain)
        sealed_billing = KEEP
        if billing is None:
            sealed_billing = None
        elif billing is not KEEP:
            sealed_billing = await self._seal_billing(spec, billing)
        await self._repo.update_key(key_id, self._clock.now_ms(), label=label, key=sealed_key, billing=sealed_billing)

    async def remove_key(self, user: User, key_id: int) -> None:
        require_admin(user)
        await self._repo.delete_key(key_id)

    def _billing_from(self, spec: ProviderSpec, raw: object, errors: list[str]):
        """(secret values, plain values) of a billing credential, or None for none."""
        if raw is None:
            return None
        if not spec.billing_fields:
            errors.append(f"{spec.label} keys take no billing credential")
            return None
        return read_fields(spec.billing_fields, raw, "billing", errors)

    async def _seal_billing(self, spec: ProviderSpec, billing: tuple[dict, dict]) -> tuple[str, dict]:
        secrets, plain = billing
        return await self._ring.seal_billing(spec.id, secrets), plain

    async def check(self, user: User, key_id: int) -> CheckResult:
        """Probe the key now (clearing or setting its out-of-credit or refused mark), and
        read the provider's budget figure where it can report one."""
        require_admin(user)
        key = await self._repo.get_key(key_id)
        now = self._clock.now_ms()
        result = await self._probe(user, key, now)
        await self._repo.record_check(key.id, now, result)
        balance_error = None
        if self._ring.reads_balance(key):
            balance_error = await self._read_balance(key, now)
        return CheckResult(result, balance_error)

    async def _probe(self, user: User, key: EvaluatorKey, now: int) -> str:
        evaluator = await self._ring.evaluator(key)
        if isinstance(evaluator, str):
            return evaluator
        spec = self._ring.providers[key.provider]
        entry = next((e for e in await self._repo.list_entries() if e.key_id == key.id), None)
        model = entry.model if entry else spec.probe_model
        if model is None:
            return CHECK_NEEDS_ENTRY
        reserved = (cost_micros(entry, _PROBE_INPUT_TOKENS, _PROBE_OUTPUT_TOKENS) if entry else 0)
        token = uuid4().hex
        await self._repo.reserve(Reservation(
            token=token, entry_id=entry.id if entry else None, key_id=key.id, provider=key.provider, model=model,
            attempt_id=None, user_email=user.email, trigger=CHECK, day=utc_day(now), month=utc_month(now),
            reserved_micros=reserved, rubric=RUBRIC_VERSION, created_at=now,
        ), None, None, None)
        try:
            reply = await evaluator.probe(model)
        except Exception:
            reply = None
        if reply is None:
            await self._repo.settle(token, Settlement(reserved, 0, 0, 0, None, None, "error"))
            return "the check failed"
        cost = reserved if reply.usage_unknown or entry is None else cost_micros(
            entry, reply.input_tokens, reply.output_tokens)
        await self._repo.settle(token, Settlement(
            cost, reply.input_tokens, reply.output_tokens, reply.latency_ms, reply.http_status,
            reply.request_id, reply.outcome,
        ))
        if reply.outcome in (OUT_OF_CREDIT, KEY_REFUSED):
            await self._repo.mark_key(key.id, reply.outcome, now)
            return UNUSABLE_REASONS[reply.outcome]
        if reply.answered:
            await self._repo.mark_key(key.id, None, None)
            return CHECK_WORKING
        return f"provider error ({reply.http_status})" if reply.http_status else "the provider did not answer"

    async def _read_balance(self, key: EvaluatorKey, now: int) -> str | None:
        spec = self._ring.providers[key.provider]
        try:
            values = await self._ring.balance_values(key)
            reading = await spec.read_balance(values, self._ring.send, now)
        except BillingError as e:
            error = str(e)
        except Exception:  # an unreadable credential, or a bug: say so without detail
            error = "the billing credential could not be used"
        else:
            await self._repo.record_balance(key.id, now, StoredBalance(
                reading.limit_micros, reading.spent_micros, reading.currency, reading.source), None)
            return None
        await self._repo.record_balance(key.id, now, None, error)
        return error

    # -- entries -------------------------------------------------------------

    async def add_entry(self, user: User, payload: object) -> int:
        """``{key_id, model, monthly_cap_usd (null for none), input_price_per_mtok,
        output_price_per_mtok}``."""
        require_admin(user)
        body = payload if isinstance(payload, dict) else {}
        errors: list[str] = []
        key_id = body.get("key_id")
        if isinstance(key_id, bool) or not isinstance(key_id, int):
            errors.append("key_id must be one of the keys' ids")
        model = body.get("model")
        if not isinstance(model, str) or not re.match(_MODEL_ID, model.strip()):
            errors.append("model must be a model id (letters, digits and . _ : / @ -), at most 120 characters")
        cap, input_price, output_price = _entry_money(body, errors)
        if errors:
            raise Invalid("; ".join(errors))
        return await self._repo.add_entry(key_id, model.strip(), cap, input_price, output_price, self._clock.now_ms())

    async def update_entry(self, user: User, entry_id: int, payload: object) -> None:
        require_admin(user)
        errors: list[str] = []
        cap, input_price, output_price = _entry_money(payload if isinstance(payload, dict) else {}, errors)
        if errors:
            raise Invalid("; ".join(errors))
        await self._repo.update_entry(entry_id, cap, input_price, output_price, self._clock.now_ms())

    async def remove_entry(self, user: User, entry_id: int) -> None:
        require_admin(user)
        await self._repo.delete_entry(entry_id)

    async def reorder(self, user: User, payload: object) -> None:
        """``{"ids": [...]}``: every entry's id exactly once, first to last."""
        require_admin(user)
        ids = payload.get("ids") if isinstance(payload, dict) else None
        current = [e.id for e in await self._repo.list_entries()]
        if (not isinstance(ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in ids)
                or sorted(ids) != sorted(current)):
            raise Invalid("ids must list every evaluator exactly once")
        await self._repo.reorder(ids, self._clock.now_ms())



def raise_no_storage():
    raise Conflict(f"{NO_KEY_STORAGE}: the owner must set that Worker secret before keys can be stored")
