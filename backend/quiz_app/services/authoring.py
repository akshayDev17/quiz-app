"""Authoring: import a set from JSON, then publish, archive or clone it. Admins only.

v1 has no edit: clone is how a set is revised.
"""

from __future__ import annotations

from ..clock import Clock
from ..errors import Forbidden, NotFound
from ..models import QuizSetInfo, User
from ..ports import QuizAuthoring
from ..validation import QuestionImport, QuizValidator


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise Forbidden("admin only")


class AuthoringService:
    def __init__(self, repo: QuizAuthoring, clock: Clock):
        self._repo = repo
        self._clock = clock

    async def import_set(self, user: User, payload: dict) -> QuizSetInfo:
        _require_admin(user)
        imp = QuizValidator.parse(payload)
        set_id = await self._repo.create_set(imp, user.email, self._clock.now_ms())
        return await self._existing(set_id)

    async def publish(self, user: User, set_id: int) -> QuizSetInfo:
        return await self._set_status(user, set_id, "published")

    async def archive(self, user: User, set_id: int) -> QuizSetInfo:
        return await self._set_status(user, set_id, "archived")

    async def clone(self, user: User, set_id: int) -> QuizSetInfo:
        _require_admin(user)
        await self._existing(set_id)
        new_id = await self._repo.clone(set_id, user.email, self._clock.now_ms())
        return await self._existing(new_id)

    async def delete(self, user: User, set_id: int) -> None:
        _require_admin(user)
        await self._existing(set_id)
        await self._repo.delete(set_id)

    async def update(self, user: User, set_id: int, payload: dict) -> QuizSetInfo:
        _require_admin(user)
        await self._existing(set_id)
        imp = QuizValidator.parse_update(payload)
        await self._repo.update(set_id, imp, self._clock.now_ms())
        return await self._existing(set_id)

    async def detail(self, user: User, set_id: int) -> tuple[QuizSetInfo, list[QuestionImport]]:
        _require_admin(user)
        info = await self._existing(set_id)
        return info, await self._repo.questions(set_id)

    async def list_all(self, user: User) -> list[tuple[QuizSetInfo, int]]:
        _require_admin(user)
        return await self._repo.list_all()

    async def _set_status(self, user: User, set_id: int, status: str) -> QuizSetInfo:
        _require_admin(user)
        await self._existing(set_id)
        await self._repo.set_status(set_id, status)
        return await self._existing(set_id)

    async def _existing(self, set_id: int) -> QuizSetInfo:
        info = await self._repo.get(set_id)
        if info is None:
            raise NotFound("quiz set not found")
        return info
