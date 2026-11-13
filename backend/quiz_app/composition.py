"""Wires the D1 repositories, services and router together.

Shared by the Worker (``entry.py``) and the local server so both run the same graph
with one ``Clock`` instance (repositories and services must agree on the time).

Evaluator keys live in D1, sealed under ``cipher`` (``keycipher``; ``None`` when the
``KEY_ENCRYPTION_KEY`` secret is not set, so no key can be stored or used and written
answers wait). ``providers`` are the provider specs keys can be entered for (the real ones
by default; tests and the local server add the fake), and ``send`` is the outbound HTTP
they use. ``settings`` are the numbers kept as configuration; ``settings_from`` reads them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .api import Api
from .clock import Clock, SystemClock
from .d1.attempts import D1AttemptRepository
from .d1.authoring import D1QuizAuthoring
from .d1.catalog import D1Catalog, D1PaperSource
from .d1.evaluations import D1EvaluationRepository
from .d1.users import D1UserRepository
from .evaluators import PROVIDERS, ProviderSpec
from .keycipher import KeyCipher
from .services.attempts import AttemptService
from .services.authoring import AuthoringService
from .services.catalog import PublicCatalogService
from .services.evaluation import EvaluationService, EvaluationSettings
from .services.evaluator_admin import EvaluatorAdmin
from .services.keyring import KeyRing
from .services.users import UserService
from .transport import HttpSend


def settings_from(read_setting: Callable[[str], str | None]) -> EvaluationSettings:
    """The owner's open numbers, as Worker vars (``wrangler.jsonc``), each falling back to
    its default when missing or malformed:

    * ``EVAL_USER_DAILY_LIMIT``, ``EVAL_GLOBAL_DAILY_LIMIT``: whole numbers of evaluations
      (model calls, one per attempt) per UTC day;
    * ``EVAL_DEFAULT_MONTHLY_CAP_USD``: the cap prefilled for a new entry."""
    defaults = EvaluationSettings()

    def number(name: str, default, kind, low, high):
        raw = read_setting(name)
        try:
            value = kind(str(raw).strip()) if raw is not None else default
        except ValueError:
            return default
        return value if low <= value <= high else default

    return EvaluationSettings(
        user_daily=number("EVAL_USER_DAILY_LIMIT", defaults.user_daily, int, 0, 1_000_000),
        global_daily=number("EVAL_GLOBAL_DAILY_LIMIT", defaults.global_daily, int, 0, 1_000_000),
        default_cap_usd=number("EVAL_DEFAULT_MONTHLY_CAP_USD", defaults.default_cap_usd, float, 0, 10_000),
    )


async def _no_network(method, url, headers, body, timeout_s):
    raise RuntimeError("no outbound HTTP configured")


def build_api(
    db,
    admin_emails: Iterable[str],
    clock: Clock | None = None,
    cipher: KeyCipher | None = None,
    providers: dict[str, ProviderSpec] | None = None,
    send: HttpSend | None = None,
    settings: EvaluationSettings | None = None,
    log: Callable[[str], None] = print,
) -> Api:
    clock = clock or SystemClock()
    settings = settings or EvaluationSettings()
    attempts_repo = D1AttemptRepository(db)
    evaluation_repo = D1EvaluationRepository(db)
    ring = KeyRing(PROVIDERS if providers is None else providers, cipher, send or _no_network)
    evaluation = EvaluationService(evaluation_repo, attempts_repo, ring, clock, settings, log=log)
    return Api(
        users=UserService(D1UserRepository(db, clock), frozenset(admin_emails)),
        authoring=AuthoringService(D1QuizAuthoring(db, clock), clock),
        attempts=AttemptService(
            D1Catalog(db), D1PaperSource(db), attempts_repo, clock, evaluation=evaluation,
        ),
        public=PublicCatalogService(D1Catalog(db), D1PaperSource(db)),
        evaluation=evaluation,
        evaluators=EvaluatorAdmin(evaluation_repo, ring, clock, settings),
    )
