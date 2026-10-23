"""D1-backed users."""

from __future__ import annotations

from ..clock import Clock
from ..models import User
from ..ports import UserRepository


class D1UserRepository(UserRepository):
    """``role`` is always stored as ``solver``; admin status is decided by
    ``UserService`` from the ``ADMIN_EMAILS`` secret, never persisted."""

    def __init__(self, db, clock: Clock):
        self._db = db
        self._clock = clock

    async def get_or_create(self, email: str) -> User:
        await self._db.prepare(
            "INSERT INTO users (email, role, created_at) VALUES (?, 'solver', ?) "
            "ON CONFLICT(email) DO NOTHING"
        ).bind(email, self._clock.now_ms()).run()
        return await self._get(email)

    async def set_display_name(self, email: str, name: str) -> User:
        await self.get_or_create(email)
        await self._db.prepare("UPDATE users SET display_name = ? WHERE email = ?").bind(name, email).run()
        return await self._get(email)

    async def _get(self, email: str) -> User:
        row = await self._db.prepare(
            "SELECT email, display_name, role FROM users WHERE email = ?"
        ).bind(email).first()
        return User(email=row["email"], display_name=row["display_name"], role=row["role"])
