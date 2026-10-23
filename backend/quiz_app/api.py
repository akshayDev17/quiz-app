"""The HTTP API as a pure function of (method, path, body, identity).

No framework and no I/O of its own: the Worker and the local server each turn a
real request into these four arguments and the returned ``(status, body)`` back
into a real response. Every route needs an identity and upserts the user first.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

from . import serializers
from .auth import Identity
from .errors import Conflict, Forbidden, Invalid, NotFound, QuizError
from .models import User
from .services.attempts import AttemptService
from .services.authoring import AuthoringService
from .services.users import UserService

PREFIX = "/quiz/api"

_STATUS = {NotFound: 404, Conflict: 409, Invalid: 422, Forbidden: 403}


def _status_of(error: QuizError) -> int:
    return next((code for kind, code in _STATUS.items() if isinstance(error, kind)), 500)


class _Malformed:
    """Marks a request body that was not valid JSON (distinct from an absent body)."""

    def __repr__(self) -> str:
        return "MALFORMED"


MALFORMED = _Malformed()


def decode_body(raw: str | bytes | None) -> object:
    """A request body as JSON: ``None`` when empty, :data:`MALFORMED` when it does not parse."""
    if raw is None or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return MALFORMED


Response = tuple[int, dict | None]
Handler = Callable[..., Awaitable[Response]]


def _object(body: object) -> dict:
    if not isinstance(body, dict):
        raise Invalid("request body must be a JSON object")
    return body


def _option_ids(body: object) -> list[int]:
    ids = _object(body).get("option_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise Invalid("option_ids must be a list of integers")
    return ids


class Api:
    def __init__(self, users: UserService, authoring: AuthoringService, attempts: AttemptService):
        self._users = users
        self._authoring = authoring
        self._attempts = attempts
        sid, aid, qid = r"(\d{1,15})", r"([^/]{1,64})", r"(\d{1,15})"
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = [
            (method, re.compile(f"^{pattern}$"), handler)
            for method, pattern, handler in [
                ("GET", "/me", self._get_me),
                ("PATCH", "/me", self._rename),
                ("GET", "/topics", self._topics),
                ("GET", f"/sets/{sid}", self._set_intro),
                ("POST", f"/sets/{sid}/attempts", self._start),
                ("GET", "/attempts", self._history),
                ("GET", f"/attempts/{aid}", self._attempt),
                ("PUT", f"/attempts/{aid}/answers/{qid}", self._answer),
                ("POST", f"/attempts/{aid}/submit", self._submit),
                ("GET", f"/attempts/{aid}/results", self._results),
                ("GET", "/admin/sets", self._admin_list),
                ("POST", "/admin/sets", self._admin_import),
                ("POST", f"/admin/sets/{sid}/publish", self._admin_publish),
                ("POST", f"/admin/sets/{sid}/archive", self._admin_archive),
                ("POST", f"/admin/sets/{sid}/clone", self._admin_clone),
            ]
        ]

    async def handle(self, method: str, path: str, body: object, identity: Identity | None) -> Response:
        """``path`` is the full request path, without query string."""
        local = path.rstrip("/")
        if local != PREFIX and not local.startswith(PREFIX + "/"):
            return 404, {"error": "not found"}
        if identity is None:
            return 401, {"error": "sign-in required"}
        local = local[len(PREFIX):]
        try:
            user = await self._users.me(identity)
            for route_method, pattern, handler in self._routes:
                match = pattern.match(local)
                if match and route_method == method.upper():
                    return await handler(user, body, *match.groups())
        except QuizError as e:
            return _status_of(e), {"error": e.message}
        return 404, {"error": "not found"}

    # -- me ------------------------------------------------------------------

    async def _get_me(self, user: User, body: object) -> Response:
        return 200, serializers.me(user)

    async def _rename(self, user: User, body: object) -> Response:
        renamed = await self._users.rename(Identity(user.email), _object(body).get("display_name"))
        return 200, serializers.me(renamed)

    # -- solver --------------------------------------------------------------

    async def _topics(self, user: User, body: object) -> Response:
        return 200, serializers.topics(*await self._attempts.overview(user.email))

    async def _set_intro(self, user: User, body: object, set_id: str) -> Response:
        return 200, serializers.set_intro(*await self._attempts.intro(user.email, int(set_id)))

    async def _start(self, user: User, body: object, set_id: str) -> Response:
        session = await self._attempts.start_or_resume(user.email, int(set_id))
        return (201 if session.created else 200), serializers.attempt_session(session)

    async def _history(self, user: User, body: object) -> Response:
        return 200, serializers.history(await self._attempts.history(user.email))

    async def _attempt(self, user: User, body: object, attempt_id: str) -> Response:
        return 200, serializers.attempt_session(await self._attempts.session(user.email, attempt_id))

    async def _answer(self, user: User, body: object, attempt_id: str, question_id: str) -> Response:
        await self._attempts.save(user.email, attempt_id, int(question_id), _option_ids(body))
        return 204, None

    async def _submit(self, user: User, body: object, attempt_id: str) -> Response:
        attempt = await self._attempts.submit(user.email, attempt_id)
        return 200, {"attempt_id": attempt.id, "status": attempt.status}

    async def _results(self, user: User, body: object, attempt_id: str) -> Response:
        return 200, serializers.results(await self._attempts.results(user.email, attempt_id))

    # -- admin ---------------------------------------------------------------

    async def _admin_list(self, user: User, body: object) -> Response:
        return 200, serializers.admin_sets(await self._authoring.list_all(user))

    async def _admin_import(self, user: User, body: object) -> Response:
        # The service checks the role before it looks at the payload.
        info = await self._authoring.import_set(user, body)
        return 201, {"id": info.id, "name": info.name}

    async def _admin_publish(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.publish(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}

    async def _admin_archive(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.archive(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}

    async def _admin_clone(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.clone(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}
