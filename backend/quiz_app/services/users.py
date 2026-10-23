"""Users: the signed-in person, their role and their display name."""

from __future__ import annotations

from dataclasses import replace

from ..auth import Identity, normalize_email
from ..errors import Invalid
from ..models import User
from ..ports import UserRepository

DISPLAY_NAME_MAX = 60


class UserService:
    def __init__(self, repo: UserRepository, admin_emails: frozenset[str]):
        self._repo = repo
        self._admins = frozenset(normalize_email(email) for email in admin_emails)

    async def me(self, identity: Identity) -> User:
        return self._with_role(await self._repo.get_or_create(identity.email))

    async def rename(self, identity: Identity, raw: str) -> User:
        name = raw.strip() if isinstance(raw, str) else ""
        if not 1 <= len(name) <= DISPLAY_NAME_MAX:
            raise Invalid(f"display name must be 1-{DISPLAY_NAME_MAX} characters")
        return self._with_role(await self._repo.set_display_name(identity.email, name))

    def _with_role(self, user: User) -> User:
        """Admin status comes from the ``ADMIN_EMAILS`` secret, overriding the stored role."""
        return replace(user, role="admin" if user.email in self._admins else "solver")
