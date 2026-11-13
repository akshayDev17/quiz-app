"""The HTTP API as a pure function of (method, path, body, identity).

No framework and no I/O of its own: the Worker and the local server each turn a
real request into these four arguments and the returned ``(status, body)`` back
into a real response (with :func:`response_headers`). Every route needs an identity
and upserts the user first, except the read-only ``/public/*`` routes: they answer
anyone, never look at the identity, and serve nothing of any person.
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
from .services.catalog import PublicCatalogService
from .services.evaluation import EvaluationService
from .services.evaluator_admin import EvaluatorAdmin
from .services.users import UserService

PREFIX = "/quiz/api"
PUBLIC = PREFIX + "/public"

#: Public reads change only when an admin publishes, so a minute of caching is safe.
PUBLIC_CACHE = "public, max-age=60"

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


def _local(path: str) -> str:
    return path.rstrip("/")


def is_public(path: str) -> bool:
    """Whether ``path`` (without query string) is in the identity-free ``/public`` namespace."""
    local = _local(path)
    return local == PUBLIC or local.startswith(PUBLIC + "/")


def response_headers(path: str, status: int) -> dict[str, str]:
    """Headers beyond content-type that :meth:`Api.handle`'s answer for ``path`` needs."""
    if not is_public(path):
        return {}
    if status == 200:
        return {"cache-control": PUBLIC_CACHE}
    if status == 405:
        return {"allow": "GET"}
    return {}


def _object(body: object) -> dict:
    if not isinstance(body, dict):
        raise Invalid("request body must be a JSON object")
    return body


def _is_id_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(i, int) and not isinstance(i, bool) for i in value)


def _answer_of(item: dict) -> frozenset[int] | str:
    """One answer: ``{"option_ids": [...]}`` for a choice question, ``{"text": "..."}`` for
    a subjective one. Whether it suits its question is the service's call."""
    if "text" in item:
        if "option_ids" in item:
            raise Invalid("an answer has option_ids or text, not both")
        if not isinstance(item["text"], str):
            raise Invalid("text must be a string")
        return item["text"]
    option_ids = item.get("option_ids")
    if not _is_id_list(option_ids):
        raise Invalid("option_ids must be a list of integers")
    return frozenset(option_ids)


def _answers(body: object) -> tuple[dict[int, frozenset[int]], dict[int, str]]:
    """``{"answers": [{"question_id": 1, "option_ids": [2, 3]}, {"question_id": 4, "text": "…"}]}``
    as (ticked, typed); an absent body is no answers."""
    if body is None:
        return {}, {}
    raw = _object(body).get("answers", [])
    if not isinstance(raw, list):
        raise Invalid("answers must be a list")
    ticked: dict[int, frozenset[int]] = {}
    typed: dict[int, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise Invalid("each answer must be an object")
        question_id = item.get("question_id")
        if not isinstance(question_id, int) or isinstance(question_id, bool):
            raise Invalid("question_id must be an integer")
        answer = _answer_of(item)
        if isinstance(answer, str):
            typed[question_id] = answer
        else:
            ticked[question_id] = answer
    return ticked, typed


class Api:
    def __init__(
        self,
        users: UserService,
        authoring: AuthoringService,
        attempts: AttemptService,
        public: PublicCatalogService,
        evaluation: EvaluationService,
        evaluators: EvaluatorAdmin,
    ):
        self._users = users
        self._authoring = authoring
        self._attempts = attempts
        self._public = public
        self._evaluation = evaluation
        self._evaluators = evaluators
        sid, aid, qid = r"(\d{1,15})", r"([^/]{1,64})", r"(\d{1,15})"
        #: GET only, relative to /public. Handlers take no user.
        self._public_routes: list[tuple[re.Pattern[str], Handler]] = [
            (re.compile(f"^{pattern}$"), handler)
            for pattern, handler in [
                ("/topics", self._public_topics),
                (f"/sets/{sid}", self._public_set),
            ]
        ]
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
                ("POST", f"/attempts/{aid}/pause", self._pause),
                ("POST", f"/attempts/{aid}/resume", self._resume),
                ("GET", f"/attempts/{aid}/results", self._results),
                ("GET", "/admin/sets", self._admin_list),
                ("POST", "/admin/sets", self._admin_import),
                ("GET", f"/admin/sets/{sid}", self._admin_get_set),
                ("PUT", f"/admin/sets/{sid}", self._admin_update),
                ("POST", f"/admin/sets/{sid}/publish", self._admin_publish),
                ("POST", f"/admin/sets/{sid}/archive", self._admin_archive),
                ("POST", f"/admin/sets/{sid}/visibility", self._admin_visibility),
                ("POST", f"/admin/sets/{sid}/clone", self._admin_clone),
                ("DELETE", f"/admin/sets/{sid}", self._admin_delete),
                # The AI evaluators of written answers: admins only, checked in the services.
                ("GET", "/admin/evaluators", self._admin_evaluators),
                ("POST", "/admin/evaluators", self._admin_add_entry),
                ("POST", "/admin/evaluators/order", self._admin_order_entries),
                ("PUT", f"/admin/evaluators/{sid}", self._admin_update_entry),
                ("DELETE", f"/admin/evaluators/{sid}", self._admin_remove_entry),
                ("POST", "/admin/evaluators/keys", self._admin_add_key),
                ("PUT", f"/admin/evaluators/keys/{sid}", self._admin_update_key),
                ("DELETE", f"/admin/evaluators/keys/{sid}", self._admin_remove_key),
                ("POST", f"/admin/evaluators/keys/{sid}/check", self._admin_check_key),
                ("POST", "/admin/evaluations/rerun", self._admin_rerun),
            ]
        ]

    async def handle(self, method: str, path: str, body: object, identity: Identity | None) -> Response:
        """``path`` is the full request path, without query string."""
        local = _local(path)
        if local != PREFIX and not local.startswith(PREFIX + "/"):
            return 404, {"error": "not found"}
        if is_public(local):
            return await self._handle_public(method, local[len(PUBLIC):])
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

    async def _handle_public(self, method: str, local: str) -> Response:
        """Matched before the identity check, so it must never touch a user: no ``users.me``."""
        if method.upper() != "GET":
            return 405, {"error": "method not allowed"}
        try:
            for pattern, handler in self._public_routes:
                match = pattern.match(local)
                if match:
                    return await handler(*match.groups())
        except QuizError as e:
            return _status_of(e), {"error": e.message}
        return 404, {"error": "not found"}

    # -- public --------------------------------------------------------------

    async def _public_topics(self) -> Response:
        return 200, serializers.public_topics(await self._public.published())

    async def _public_set(self, set_id: str) -> Response:
        return 200, serializers.public_set(*await self._public.view(int(set_id)))

    # -- me ------------------------------------------------------------------

    async def _get_me(self, user: User, body: object) -> Response:
        return 200, serializers.me(user)

    async def _rename(self, user: User, body: object) -> Response:
        renamed = await self._users.rename(Identity(user.email), _object(body).get("display_name"))
        return 200, serializers.me(renamed)

    # -- solver --------------------------------------------------------------

    async def _topics(self, user: User, body: object) -> Response:
        return 200, serializers.topics(
            *await self._attempts.overview(user.email, include_private=user.can_edit_sets)
        )

    async def _set_intro(self, user: User, body: object, set_id: str) -> Response:
        return 200, serializers.set_intro(
            *await self._attempts.intro(user.email, int(set_id), include_private=user.can_edit_sets)
        )

    async def _start(self, user: User, body: object, set_id: str) -> Response:
        session = await self._attempts.start_or_resume(
            user.email, int(set_id), include_private=user.can_edit_sets
        )
        return (201 if session.created else 200), serializers.attempt_session(session)

    async def _history(self, user: User, body: object) -> Response:
        return 200, serializers.history(*await self._attempts.history(user.email))

    async def _attempt(self, user: User, body: object, attempt_id: str) -> Response:
        return 200, serializers.attempt_session(await self._attempts.session(user.email, attempt_id))

    async def _answer(self, user: User, body: object, attempt_id: str, question_id: str) -> Response:
        answer = _answer_of(_object(body))
        if isinstance(answer, str):
            await self._attempts.save_text(user.email, attempt_id, int(question_id), answer)
        else:
            await self._attempts.save(user.email, attempt_id, int(question_id), sorted(answer))
        return 204, None

    async def _submit(self, user: User, body: object, attempt_id: str) -> Response:
        # Admins are exempt from the per-person daily evaluation limit.
        attempt = await self._attempts.submit(user.email, attempt_id, quota_exempt=user.can_edit_sets)
        return 200, {"attempt_id": attempt.id, "status": attempt.status}

    async def _results(self, user: User, body: object, attempt_id: str) -> Response:
        return 200, serializers.results(await self._attempts.results(user.email, attempt_id))

    async def _pause(self, user: User, body: object, attempt_id: str) -> Response:
        # The body carries whatever the solver had not yet saved, so the freeze and
        # those answers commit together instead of the freeze racing an autosave.
        ticked, typed = _answers(body)
        return 200, serializers.attempt_session(
            await self._attempts.pause(user.email, attempt_id, ticked, typed)
        )

    async def _resume(self, user: User, body: object, attempt_id: str) -> Response:
        return 200, serializers.attempt_session(await self._attempts.resume(user.email, attempt_id))

    # -- admin ---------------------------------------------------------------

    async def _admin_list(self, user: User, body: object) -> Response:
        return 200, serializers.admin_sets(await self._authoring.list_all(user))

    async def _admin_import(self, user: User, body: object) -> Response:
        # The service checks the role before it looks at the payload.
        info = await self._authoring.import_set(user, body)
        return 201, {"id": info.id, "name": info.name}

    async def _admin_get_set(self, user: User, body: object, set_id: str) -> Response:
        info, questions = await self._authoring.detail(user, int(set_id))
        return 200, serializers.admin_set_detail(info, questions)

    async def _admin_update(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.update(user, int(set_id), body)
        return 200, {"id": info.id, "name": info.name}

    async def _admin_publish(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.publish(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}

    async def _admin_archive(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.archive(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}

    async def _admin_visibility(self, user: User, body: object, set_id: str) -> Response:
        # The service checks the role before it looks at the payload.
        info = await self._authoring.set_visibility(user, int(set_id), body)
        return 200, {"id": info.id, "visibility": info.visibility}

    async def _admin_clone(self, user: User, body: object, set_id: str) -> Response:
        info = await self._authoring.clone(user, int(set_id))
        return 200, {"id": info.id, "status": info.status}

    async def _admin_delete(self, user: User, body: object, set_id: str) -> Response:
        await self._authoring.delete(user, int(set_id))
        return 204, None

    # -- admin: evaluators ---------------------------------------------------

    async def _page(self, user: User, status: int = 200, **extra) -> Response:
        return status, {**serializers.admin_evaluators(await self._evaluators.overview(user)), **extra}

    async def _admin_evaluators(self, user: User, body: object) -> Response:
        return await self._page(user)

    async def _admin_add_entry(self, user: User, body: object) -> Response:
        await self._evaluators.add_entry(user, body)
        return await self._page(user, 201)

    async def _admin_update_entry(self, user: User, body: object, entry_id: str) -> Response:
        await self._evaluators.update_entry(user, int(entry_id), body)
        return await self._page(user)

    async def _admin_remove_entry(self, user: User, body: object, entry_id: str) -> Response:
        await self._evaluators.remove_entry(user, int(entry_id))
        return await self._page(user)

    async def _admin_order_entries(self, user: User, body: object) -> Response:
        await self._evaluators.reorder(user, body)
        return await self._page(user)

    async def _admin_add_key(self, user: User, body: object) -> Response:
        await self._evaluators.add_key(user, body)
        return await self._page(user, 201)

    async def _admin_update_key(self, user: User, body: object, key_id: str) -> Response:
        await self._evaluators.update_key(user, int(key_id), body)
        return await self._page(user)

    async def _admin_remove_key(self, user: User, body: object, key_id: str) -> Response:
        await self._evaluators.remove_key(user, int(key_id))
        return await self._page(user)

    async def _admin_check_key(self, user: User, body: object, key_id: str) -> Response:
        result = await self._evaluators.check(user, int(key_id))
        return await self._page(user, check={"key_id": int(key_id), "result": result.result,
                                             "provider_budget_error": result.balance_error})

    async def _admin_rerun(self, user: User, body: object) -> Response:
        tried, awaiting = await self._evaluation.rerun(user)
        return 200, {"attempts_tried": tried, "still_awaiting": awaiting}
