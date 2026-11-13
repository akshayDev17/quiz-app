"""Who marks a written answer? An evaluator, behind a port (as identity is, ADR 0002).

``Evaluator.evaluate(request, model)`` sends one ``rubric.EvaluationRequest`` to one model
and returns an ``EvaluatorReply``: the reply text, or why there is none, plus the token
counts and the provider's request id. It never raises, never retries, and never sees a
database. What the reply means is ``rubric.parse_reply``'s business, not the adapter's.
``Evaluator.probe(model)`` sends the smallest possible request, for the admin's "check now".

Providers (``PROVIDERS``) are specs: the fields an admin pastes into the admin page for a
key (``key_fields``), an optional read-only billing credential (``billing_fields`` with
its ``read_balance``, see ``billing``), and a builder from those values to an evaluator:

* ``anthropic``: the Claude API. Field: API key. No balance API exists for it.
* ``bedrock``: Claude in Amazon Bedrock on the ``bedrock-mantle`` endpoint. Fields: a
  Bedrock API key (sent in ``x-api-key``) and the region. Billing: AWS Budgets.
* ``azure``: Claude in Microsoft Foundry. Fields: API key and the resource's endpoint
  (``https://<resource>.services.ai.azure.com/anthropic``); the model is the deployment
  name. Billing: an Azure consumption budget.

All three serve Claude through the same Messages API body, so one adapter,
``MessagesApiEvaluator``, speaks for them and only the URL and the key header differ. A
provider whose ordinary key can report its own balance needs only a ``read_balance`` that
reads ``key_fields`` and no ``billing_fields``; nothing above this module changes.

Key values are stored sealed (``keycipher``), opened only to build an adapter, sent only
in a header, and never logged, returned or put in a prompt.

``FakeEvaluator`` is the deterministic stand-in for tests and ``local_server.py``, under the
``fake`` provider that only they register (``fake_provider``).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .billing import BalanceReading, read_aws_budget, read_azure_budget
from .rubric import LEVELS, EvaluationRequest, content_words
from .transport import REQUEST_ID_HEADERS, HttpResponse, HttpSend, urllib_send

__all__ = [
    "ANTHROPIC_VERSION", "EFFORT", "REQUEST_ID_HEADERS", "HttpResponse", "HttpSend", "urllib_send",
    "OK", "REFUSAL", "TRUNCATED", "OUT_OF_CREDIT", "KEY_REFUSED", "EvaluatorReply", "Evaluator",
    "MessagesApiEvaluator", "Field", "ProviderSpec", "PROVIDERS", "FAKE", "FAKE_LABEL",
    "fake_provider", "FakeEvaluator", "foundry_messages_url", "key_hint",
]

ANTHROPIC_VERSION = "2026-10-21"
"""The ``anthropic-version`` header every Messages request sends (Claude API, Bedrock
bedrock-mantle and Foundry alike)."""

EFFORT = "low"
"""``output_config.effort``. The reply's ``analysis`` field already makes the model reason
before it picks a level; low effort keeps any extra adaptive thinking short. ``thinking``
is left at the model's default: Claude Opus 5.5 and Sonnet 5.5 reject ``disabled``."""

PROBE_MAX_TOKENS = 16
PROBE_TIMEOUT_S = 15.0


#: Outcomes. "ok" carries reply text; the model answered but its reply is unusable for
#: "refusal" and "truncated"; every other one means no answer was obtained at all.
OK, REFUSAL, TRUNCATED = "ok", "refusal", "truncated"
#: The provider refused the key's account for want of credit, or refused the key itself.
#: Neither is billed; both mark the key (every failure sends marking down the list).
OUT_OF_CREDIT, KEY_REFUSED = "out_of_credit", "key_refused"
NO_ANSWER = ("http_error", "network", "bad_envelope", "error", OUT_OF_CREDIT, KEY_REFUSED)


@dataclass(frozen=True)
class EvaluatorReply:
    outcome: str
    text: str | None = None
    http_status: int | None = None
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    #: True when the provider may have done (and billed) work whose size is unknown: a
    #: network failure or timeout. The spend reservation is then kept, not settled to 0.
    usage_unknown: bool = False

    @property
    def answered(self) -> bool:
        """Did the model answer (usable or not)? False means nothing came back to judge."""
        return self.outcome not in NO_ANSWER


class Evaluator(ABC):
    @abstractmethod
    async def evaluate(self, request: EvaluationRequest, model: str) -> EvaluatorReply:
        """Send ``request`` to ``model`` once. Must never raise and never retry."""

    @abstractmethod
    async def probe(self, model: str) -> EvaluatorReply:
        """The smallest billable request to ``model``: does this key work, with credit?
        Must never raise."""


# -- the Claude Messages API, for every provider that serves it ------------------

def failure_outcome(status: int, text: str) -> str:
    """What a non-200 reply means. 402 (``billing_error``) is a credit refusal, as is a 400
    whose message is about the credit balance (the Claude API's older form); 401 and 403
    refuse the key. Anything else is a plain error: the key is not marked."""
    error: dict = {}
    try:
        data = json.loads(text)
        error = data.get("error") if isinstance(data, dict) and isinstance(data.get("error"), dict) else {}
    except ValueError:
        pass
    kind = str(error.get("type", ""))
    message = str(error.get("message", "")).lower()
    if status == 402 or kind == "billing_error" or (status == 400 and "credit balance" in message):
        return OUT_OF_CREDIT
    if status in (401, 403) or kind in ("authentication_error", "permission_error"):
        return KEY_REFUSED
    return "http_error"


class MessagesApiEvaluator(Evaluator):
    """POSTs a Claude Messages request to ``url`` with ``auth`` (the key header) added.

    Thinking is left at the model's default and effort is low (``EFFORT``). The reply's
    format is fixed by structured outputs (``output_config.format``), which all three
    providers support for current Claude models, and validated again by the caller."""

    def __init__(self, url: str, auth: dict[str, str], send: HttpSend, clock_ms=None):
        self._url = url
        self._auth = auth
        self._send = send
        self._clock_ms = clock_ms or (lambda: time.monotonic_ns() // 1_000_000)

    def body(self, request: EvaluationRequest, model: str) -> dict:
        return {
            "model": model,
            "max_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user}],
            "output_config": {
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": request.schema},
            },
        }

    async def evaluate(self, request: EvaluationRequest, model: str) -> EvaluatorReply:
        return await self._call(self.body(request, model), request.timeout_s)

    async def probe(self, model: str) -> EvaluatorReply:
        return await self._call({
            "model": model,
            "max_tokens": PROBE_MAX_TOKENS,
            "messages": [{"role": "user", "content": "Reply with the word OK."}],
            "output_config": {"effort": EFFORT},
        }, PROBE_TIMEOUT_S)

    async def _call(self, body: dict, timeout_s: float) -> EvaluatorReply:
        headers = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
            **self._auth,
        }
        started = self._clock_ms()
        try:
            response = await self._send("POST", self._url, headers, json.dumps(body), timeout_s)
        except Exception:  # network failure or timeout: the provider may still have billed
            return EvaluatorReply("network", latency_ms=self._clock_ms() - started, usage_unknown=True)
        latency = self._clock_ms() - started
        request_id = next((response.headers[h] for h in REQUEST_ID_HEADERS if response.headers.get(h)), None)
        if response.status != 200:
            return EvaluatorReply(failure_outcome(response.status, response.text), http_status=response.status,
                                  request_id=request_id, latency_ms=latency)
        return _read_message(response.text, response.status, request_id, latency)


def _read_message(raw: str, status: int, request_id: str | None, latency: int) -> EvaluatorReply:
    """A Messages API response body as a reply: its text blocks joined, by stop reason."""
    try:
        message = json.loads(raw)
        usage = message.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        stop = message.get("stop_reason")
        text = "".join(
            block.get("text", "") for block in message.get("content") or []
            if isinstance(block, dict) and block.get("type") == "text"
        )
        request_id = request_id or (message.get("id") if isinstance(message.get("id"), str) else None)
    except (ValueError, AttributeError, TypeError):
        return EvaluatorReply("bad_envelope", http_status=status, request_id=request_id, latency_ms=latency,
                              usage_unknown=True)
    common = dict(http_status=status, request_id=request_id, input_tokens=input_tokens,
                  output_tokens=output_tokens, latency_ms=latency)
    if stop == "refusal":
        return EvaluatorReply(REFUSAL, **common)
    if stop == "max_tokens":
        return EvaluatorReply(TRUNCATED, text=text, **common)
    return EvaluatorReply(OK, text=text, **common)


# -- the fields an admin enters ----------------------------------------------------

def _token(max_length: int) -> Callable[[str], str | None]:
    """A key or secret: no spaces or control characters, 8 to ``max_length`` characters."""
    def check(value: str) -> str | None:
        value = value.strip()
        ok = 8 <= len(value) <= max_length and not any(c.isspace() or ord(c) < 32 for c in value)
        return value if ok else None
    return check


def _pattern(regex: str) -> Callable[[str], str | None]:
    compiled = re.compile(regex)

    def check(value: str) -> str | None:
        value = value.strip()
        return value if compiled.fullmatch(value) else None
    return check


def foundry_messages_url(endpoint: str) -> str | None:
    """The Messages URL for a Foundry endpoint given as the resource's ``…/anthropic`` base
    or as the full ``…/anthropic/v1/messages`` target URI. Only https."""
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint.startswith("https://") or " " in endpoint or len(endpoint) > 300:
        return None
    return endpoint if endpoint.endswith("/v1/messages") else endpoint + "/v1/messages"


def _endpoint(value: str) -> str | None:
    return value.strip().rstrip("/") if foundry_messages_url(value) else None


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    secret: bool          # sealed at rest and never shown back; plain fields are shown
    placeholder: str
    normalise: Callable[[str], str | None] = field(repr=False)
    help: str = ""

    def describe(self) -> dict:
        return {"name": self.name, "label": self.label, "secret": self.secret,
                "placeholder": self.placeholder, "help": self.help}


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    key_fields: tuple[Field, ...]
    build: Callable[[dict[str, str], HttpSend], Evaluator | None] = field(repr=False)
    #: The model a "check now" probes when no entry uses the key yet (None: needs an entry).
    probe_model: str | None = None
    #: What the page can show about money, and how: see ``billing``.
    balance_note: str = ""
    billing_label: str = ""
    billing_fields: tuple[Field, ...] = ()
    read_balance: Callable[[dict[str, str], HttpSend, int], Awaitable[BalanceReading]] | None = field(
        default=None, repr=False)


_API_KEY = Field("api_key", "API key", True, "paste the key", _token(512))


def _anthropic(values: dict[str, str], send: HttpSend) -> Evaluator:
    return MessagesApiEvaluator("https://api.anthropic.com/v1/messages", {"x-api-key": values["api_key"]}, send)


def _bedrock(values: dict[str, str], send: HttpSend) -> Evaluator:
    return MessagesApiEvaluator(
        f"https://bedrock-mantle.{values['region']}.api.aws/anthropic/v1/messages",
        {"x-api-key": values["api_key"]}, send,
    )


def _azure(values: dict[str, str], send: HttpSend) -> Evaluator | None:
    url = foundry_messages_url(values["endpoint"])
    return MessagesApiEvaluator(url, {"api-key": values["api_key"]}, send) if url else None


_GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

PROVIDERS: dict[str, ProviderSpec] = {
    spec.id: spec
    for spec in (
        ProviderSpec(
            "anthropic", "Anthropic API", (_API_KEY,), _anthropic, probe_model="claude-haiku-5-5",
            balance_note=("Anthropic has no API for an account's prepaid balance. The page shows this "
                          "month's spend from each call's tokens, and marks the key out of credit when "
                          "Anthropic refuses a call for credit."),
        ),
        ProviderSpec(
            "bedrock", "Amazon Bedrock",
            (Field("api_key", "Bedrock API key", True, "paste the key", _token(2048)),
             Field("region", "Region", False, "us-east-1", _pattern(r"[a-z]{2}(-[a-z]+)+-\d{1,2}"))),
            _bedrock, probe_model="anthropic.claude-haiku-5-5",
            balance_note="With a read-only AWS Budgets credential, the page shows the budget's own figures.",
            billing_label="AWS Budgets, read-only",
            billing_fields=(
                Field("aws_access_key_id", "Access key ID", True, "AKIA…", _pattern(r"[A-Z0-9]{16,128}"),
                      "An IAM user or role key allowed only budgets:ViewBudget."),
                Field("aws_secret_access_key", "Secret access key", True, "paste the secret", _token(128)),
                Field("account_id", "AWS account ID", False, "123456789012", _pattern(r"\d{12}")),
                Field("budget_name", "Budget name", False, "quiz-ai", _pattern(r"[^:\\\x00-\x1f]{1,100}")),
            ),
            read_balance=read_aws_budget,
        ),
        ProviderSpec(
            "azure", "Azure AI Foundry",
            (_API_KEY,
             Field("endpoint", "Endpoint", False, "https://<resource>.services.ai.azure.com/anthropic",
                   _endpoint)),
            _azure,
            balance_note="With a read-only Azure budget credential, the page shows the budget's own figures.",
            billing_label="Azure Cost Management, read-only",
            billing_fields=(
                Field("tenant_id", "Tenant ID", False, "00000000-0000-0000-0000-000000000000",
                      _pattern(rf"{_GUID}|[A-Za-z0-9.-]{{3,253}}")),
                Field("client_id", "Client ID", False, "00000000-0000-0000-0000-000000000000", _pattern(_GUID),
                      "An app registration with the Cost Management Reader role on the scope."),
                Field("client_secret", "Client secret", True, "paste the secret", _token(256)),
                Field("scope", "Scope", False, "subscriptions/<subscription id>",
                      _pattern(rf"subscriptions/{_GUID}(/resourceGroups/[-\w.()]{{1,90}})?")),
                Field("budget_name", "Budget name", False, "quiz-ai", _pattern(r"[A-Za-z0-9_-]{1,63}")),
            ),
            read_balance=read_azure_budget,
        ),
    )
}


def key_hint(values: dict[str, str]) -> str:
    """The last four characters of the key, the only part of it ever shown again."""
    key = values.get("api_key", "")
    return "…" + key[-4:] if len(key) >= 12 else ""


# -- the fake --------------------------------------------------------------------

FAKE = "fake"
FAKE_LABEL = "Fake (local)"


def fake_provider(evaluator: Evaluator) -> ProviderSpec:
    """The ``fake`` provider, registered only by tests and ``local_server.py``, never by the
    Worker. It needs no key fields; every key of it builds ``evaluator``."""
    return ProviderSpec(FAKE, FAKE_LABEL, (), lambda values, send: evaluator, probe_model="fake-overlap",
                        balance_note="Local stand-in; costs nothing.")


class FakeEvaluator(Evaluator):
    """Deterministic: an answer's level is the share of the model answer's and key points'
    content words it contains, scaled to 0–4. Not a judgment, only a stand-in so that tests
    and local runs exercise the real request, validation and storage paths.

    ``respond`` replaces the whole reply, and ``probe_reply`` a probe's, for tests of the
    failure paths."""

    def __init__(
        self,
        respond: Callable[[EvaluationRequest, str], EvaluatorReply] | None = None,
        probe_reply: Callable[[str], EvaluatorReply] | None = None,
    ):
        self._respond = respond
        self._probe_reply = probe_reply
        self.calls: list[tuple[EvaluationRequest, str]] = []
        self.probes: list[str] = []

    async def evaluate(self, request: EvaluationRequest, model: str) -> EvaluatorReply:
        self.calls.append((request, model))
        await asyncio.sleep(0)
        if self._respond is not None:
            return self._respond(request, model)
        marks = []
        for item in request.items:
            wanted = content_words(item.model_answer + " " + " ".join(item.key_points))
            found = wanted & content_words(item.answer)
            level = round(LEVELS * len(found) / len(wanted)) if wanted else 0
            marks.append({
                "id": item.key,
                "analysis": f"{len(found)} of {len(wanted)} key terms present.",
                "level": level,
                "feedback": f"Fake evaluator: your answer used {len(found)} of {len(wanted)} key terms.",
            })
        text = json.dumps({"marks": marks})
        return EvaluatorReply(
            OK, text=text, http_status=200, request_id="fake",
            input_tokens=(len(request.system) + len(request.user)) // 4,
            output_tokens=len(text) // 4,
        )

    async def probe(self, model: str) -> EvaluatorReply:
        self.probes.append(model)
        await asyncio.sleep(0)
        if self._probe_reply is not None:
            return self._probe_reply(model)
        return EvaluatorReply(OK, text="OK", http_status=200, request_id="fake", input_tokens=10, output_tokens=1)
