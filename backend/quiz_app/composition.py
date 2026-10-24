"""Wires the D1 repositories, services and router together.

Shared by the Worker (``entry.py``) and the local server so both run the same graph
with one ``Clock`` instance (repositories and services must agree on the time).
"""

from __future__ import annotations

from collections.abc import Iterable

from .api import Api
from .clock import Clock, SystemClock
from .d1.attempts import D1AttemptRepository
from .d1.authoring import D1QuizAuthoring
from .d1.catalog import D1Catalog, D1PaperSource
from .d1.users import D1UserRepository
from .services.attempts import AttemptService
from .services.authoring import AuthoringService
from .services.users import UserService


def build_api(db, admin_emails: Iterable[str], clock: Clock | None = None) -> Api:
    clock = clock or SystemClock()
    return Api(
        users=UserService(D1UserRepository(db, clock), frozenset(admin_emails)),
        authoring=AuthoringService(D1QuizAuthoring(db, clock), clock),
        attempts=AttemptService(D1Catalog(db), D1PaperSource(db), D1AttemptRepository(db), clock),
    )
