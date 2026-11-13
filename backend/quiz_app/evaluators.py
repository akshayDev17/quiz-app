"""Who marks a written answer? An evaluator, behind a port (as identity is, ADR 0002).

``Evaluator.evaluate(request, model)`` sends one ``rubric.EvaluationRequest`` to one model
and returns an ``EvaluatorReply``: the reply text, or why there is none, plus the token
counts and the provider's request id. It never raises, never retries, and never sees a
database. What the reply means is ``rubric.parse_reply``'s business, not the adapter's.

Providers (``PROVIDERS``), each a name, the Worker secrets it needs, and a builder:

* ``anthropic`` — the Claude API. Secret ``ANTHROPIC_API_KEY``.
* ``bedrock`` — Claude in Amazon Bedrock on the ``bedrock-mantle`` endpoint. Secrets
  ``BEDROCK_API_KEY`` (a Bedrock API key, sent as a bearer token in ``x-api-key``) and
  ``BEDROCK_REGION`` (e.g. ``us-east-1``).
* ``azure`` — Claude in Microsoft Foundry. Secrets ``AZURE_FOUNDRY_API_KEY`` and
  ``AZURE_FOUNDRY_ENDPOINT`` (``https://<resource>.services.ai.azure.com/anthropic``).
  The model is the deployment name.

All three serve Claude through the same Messages API body, so one adapter,
``MessagesApiEvaluator``, speaks for them and only the URL and the key header differ.
Adding a provider with the same wire format is one ``ProviderSpec``; a different wire
format (another model family's API) is one new ``Evaluator`` implementation. Nothing
above this module changes either way.

A provider is *usable* only when every secret it names is present. Secret values are read
once, in the composition root, and live only inside the adapter: they are sent in a
header, never in a URL, and are never logged, returned or put in a prompt.

``FakeEvaluator`` is the deterministic stand-in for tests and ``local_server.py``: it
answers the same request with a reply the real validator then reads.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .rubric import LEVELS, EvaluationRequest

ANTHROPIC_VERSION = "2026-10-21"
"""The ``anthropic-version`` header every Messages request sends (Claude API, Bedrock
bedrock-mantle and Foundry alike)."""

EFFORT = "low"
"""``output_config.effort``. The reply's ``analysis`` field already makes the model reason
before it picks a level; low effort keeps any extra adaptive thinking short. ``thinking``
is left at the model's default: Claude Opus 5.5 and Sonnet 5.5 reject ``disabled``."""

TIMEOUT_S = 25.0
"""One call's limit. A timed-out call is not retried: its answers wait for a re-run."""

REQUEST_ID_HEADERS = ("request-id", "x-amzn-requestid", "apim-request-id")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]   # lowercased names; only those in REQUEST_ID_HEADERS are kept
    text: str


HttpPost = Callable[[str, dict, str, float], Awaitable[HttpResponse]]
"""``post(url, headers, body, timeout_s)``. Raises on a network failure or timeout."""


#: Outcomes. "ok" carries reply text; the model answered but its reply is unusable for
#: "refusal" and "truncated"; every other one means no answer was obtained at all.
OK, REFUSAL, TRUNCATED = "ok", "refusal", "truncated"
NO_ANSWER = ("http_error", "network", "bad_envelope", "error")


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


# -- the Claude Messages API, for every provider that serves it ------------------

class MessagesApiEvaluator(Evaluator):
    """POSTs a Claude Messages request to ``url`` with ``auth`` (the key header) added.

    Thinking is left at the model's default and effort is low (``EFFORT``). The reply's
    format is fixed by structured outputs (``output_config.format``), which all three
    providers support for current Claude models, and validated again by the caller."""

    def __init__(self, url: str, auth: dict[str, str], post: HttpPost, clock_ms=None):
        self._url = url
        self._auth = auth
        self._post = post
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
        headers = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
            **self._auth,
        }
        started = self._clock_ms()
        try:
            response = await self._post(self._url, headers, json.dumps(self.body(request, model)), TIMEOUT_S)
        except Exception:  # network failure or timeout: the provider may still have billed
            return EvaluatorReply("network", latency_ms=self._clock_ms() - started, usage_unknown=True)
        latency = self._clock_ms() - started
        request_id = next((response.headers[h] for h in REQUEST_ID_HEADERS if response.headers.get(h)), None)
        if response.status != 200:
            return EvaluatorReply("http_error", http_status=response.status, request_id=request_id,
                                  latency_ms=latency)
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


# -- providers -------------------------------------------------------------------

_REGION = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d{1,2}$")


def _anthropic(secrets: dict[str, str], post: HttpPost) -> Evaluator:
    return MessagesApiEvaluator(
        "https://api.anthropic.com/v1/messages", {"x-api-key": secrets["ANTHROPIC_API_KEY"]}, post,
    )


def _bedrock(secrets: dict[str, str], post: HttpPost) -> Evaluator | None:
    region = secrets["BEDROCK_REGION"].strip()
    if not _REGION.match(region):
        return None
    return MessagesApiEvaluator(
        f"https://bedrock-mantle.{region}.api.aws/anthropic/v1/messages",
        {"x-api-key": secrets["BEDROCK_API_KEY"]}, post,
    )


def foundry_messages_url(endpoint: str) -> str | None:
    """The Messages URL for a Foundry endpoint given as the resource's ``…/anthropic`` base
    or as the full ``…/anthropic/v1/messages`` target URI. Only https."""
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint.startswith("https://") or " " in endpoint:
        return None
    return endpoint if endpoint.endswith("/v1/messages") else endpoint + "/v1/messages"


def _azure(secrets: dict[str, str], post: HttpPost) -> Evaluator | None:
    url = foundry_messages_url(secrets["AZURE_FOUNDRY_ENDPOINT"])
    if url is None:
        return None
    return MessagesApiEvaluator(url, {"api-key": secrets["AZURE_FOUNDRY_API_KEY"]}, post)


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    secrets: tuple[str, ...]
    build: Callable[[dict[str, str], HttpPost], Evaluator | None] = field(repr=False)


PROVIDERS: dict[str, ProviderSpec] = {
    spec.id: spec
    for spec in (
        ProviderSpec("anthropic", "Anthropic API", ("ANTHROPIC_API_KEY",), _anthropic),
        ProviderSpec("bedrock", "Amazon Bedrock", ("BEDROCK_API_KEY", "BEDROCK_REGION"), _bedrock),
        ProviderSpec("azure", "Azure AI Foundry", ("AZURE_FOUNDRY_API_KEY", "AZURE_FOUNDRY_ENDPOINT"), _azure),
    )
}

FAKE = "fake"
FAKE_LABEL = "Fake (local)"
"""Registered only by tests and ``local_server.py``, never by the Worker."""


def provider_label(provider: str) -> str:
    if provider == FAKE:
        return FAKE_LABEL
    spec = PROVIDERS.get(provider)
    return spec.label if spec else provider


def usable_evaluators(read_secret: Callable[[str], str | None], post: HttpPost) -> dict[str, Evaluator]:
    """The evaluator of every provider whose secrets are all present (and well formed).

    ``read_secret(name)`` returns a secret's value or ``None``. Values go straight into
    the adapters and are not kept anywhere else."""
    out: dict[str, Evaluator] = {}
    for spec in PROVIDERS.values():
        values = {}
        for name in spec.secrets:
            value = read_secret(name)
            if not value or not str(value).strip():
                break
            values[name] = str(value)
        else:
            evaluator = spec.build(values, post)
            if evaluator is not None:
                out[spec.id] = evaluator
    return out


# -- the fake --------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the and that this with from into have has had are was were will would could should "
    "their there them then than which what when where while because also only more most "
    "each other such some very just like does done been being its it's not but for you "
    "your they a an of to in on is be or by as at so if no".split()
)


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 3 and w not in _STOP}


class FakeEvaluator(Evaluator):
    """Deterministic: an answer's level is the share of the model answer's and key points'
    content words it contains, scaled to 0–4. Not a judgment, only a stand-in so that tests
    and local runs exercise the real request, validation and storage paths.

    ``respond`` replaces the whole reply, for tests of the failure paths."""

    def __init__(self, respond: Callable[[EvaluationRequest, str], EvaluatorReply] | None = None):
        self._respond = respond
        self.calls: list[tuple[EvaluationRequest, str]] = []

    async def evaluate(self, request: EvaluationRequest, model: str) -> EvaluatorReply:
        self.calls.append((request, model))
        await asyncio.sleep(0)
        if self._respond is not None:
            return self._respond(request, model)
        marks = []
        for item in request.items:
            wanted = _terms(item.model_answer + " " + " ".join(item.key_points))
            found = wanted & _terms(item.answer)
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


# -- a stdlib transport, for local runs (never the Worker) ---------------------

async def urllib_post(url: str, headers: dict, body: str, timeout_s: float) -> HttpResponse:
    """``HttpPost`` over ``urllib``, run in a thread. For ``local_server.py`` and dev tools."""
    import urllib.error
    import urllib.request

    def call() -> HttpResponse:
        request = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 (https only)
                status, raw, got = response.status, response.read(), response.headers
        except urllib.error.HTTPError as e:
            status, raw, got = e.code, e.read(), e.headers
        kept = {h: got.get(h) for h in REQUEST_ID_HEADERS if got.get(h)}
        return HttpResponse(status, kept, raw.decode("utf-8", "replace"))

    return await asyncio.get_running_loop().run_in_executor(None, call)
