"""Wires the D1 repositories, services and router together.

Shared by the Worker (``entry.py``) and the local server so both run the same graph
with one ``Clock`` instance (repositories and services must agree on the time).

``evaluators`` are the usable evaluator of each provider whose secrets are present (see
``evaluators.usable_evaluators``); without any, written answers wait, awaiting evaluation.
``quotas`` are the daily evaluation limits; ``quotas_from`` reads them from settings.
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
from .evaluators import Evaluator
from .services.attempts import AttemptService
from .services.authoring import AuthoringService
from .services.catalog import PublicCatalogService
from .services.evaluation import EvaluationService, Quotas
from .services.users import UserService


def quotas_from(read_setting: Callable[[str], str | None]) -> Quotas:
    """``EVAL_USER_DAILY_LIMIT`` and ``EVAL_GLOBAL_DAILY_LIMIT``: whole numbers of evaluations
    (model calls, one per attempt) per UTC day. Missing or malformed means the default."""
    defaults = Quotas()

    def whole(name: str, default: int) -> int:
        raw = read_setting(name)
        try:
            value = int(str(raw).strip()) if raw is not None else default
        except ValueError:
            return default
        return value if value >= 0 else default

    return Quotas(
        user_daily=whole("EVAL_USER_DAILY_LIMIT", defaults.user_daily),
        global_daily=whole("EVAL_GLOBAL_DAILY_LIMIT", defaults.global_daily),
    )


def build_api(
    db,
    admin_emails: Iterable[str],
    clock: Clock | None = None,
    evaluators: dict[str, Evaluator] | None = None,
    quotas: Quotas | None = None,
    log: Callable[[str], None] = print,
) -> Api:
    clock = clock or SystemClock()
    attempts_repo = D1AttemptRepository(db)
    evaluation = EvaluationService(
        D1EvaluationRepository(db), attempts_repo, evaluators or {}, clock, quotas, log=log,
    )
    return Api(
        users=UserService(D1UserRepository(db, clock), frozenset(admin_emails)),
        authoring=AuthoringService(D1QuizAuthoring(db, clock), clock),
        attempts=AttemptService(
            D1Catalog(db), D1PaperSource(db), attempts_repo, clock, evaluation=evaluation,
        ),
        public=PublicCatalogService(D1Catalog(db), D1PaperSource(db)),
        evaluation=evaluation,
    )
