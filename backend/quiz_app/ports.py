"""Ports: what the services need from storage. D1 implements them (``quiz_app.d1``)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import QuestionForSolver, QuestionKey, QuizSetInfo, ReviewQuestion, User
from .validation import SetImport


class UserRepository(ABC):
    @abstractmethod
    async def get_or_create(self, email: str) -> User:
        """The stored user, created as a ``solver`` on first sight."""

    @abstractmethod
    async def set_display_name(self, email: str, name: str) -> User:
        """Store an already-validated display name; creates the user if absent."""


class QuizCatalog(ABC):
    @abstractmethod
    async def list_published(self) -> list[QuizSetInfo]: ...

    @abstractmethod
    async def get_set(self, set_id: int) -> QuizSetInfo | None: ...

    @abstractmethod
    async def questions_for_solver(self, set_id: int) -> list[QuestionForSolver]: ...


class AnswerKeyReader(ABC):
    @abstractmethod
    async def answer_key(self, set_id: int) -> list[QuestionKey]: ...

    @abstractmethod
    async def review_questions(self, set_id: int) -> list[ReviewQuestion]: ...


class QuizAuthoring(ABC):
    @abstractmethod
    async def create_set(self, imp: SetImport, created_by: str, now_ms: int) -> int:
        """Store an import as a draft, numbered max(seq)+1 in its bucket; returns the new id."""

    @abstractmethod
    async def set_status(self, set_id: int, status: str) -> None: ...

    @abstractmethod
    async def clone(self, set_id: int, created_by: str, now_ms: int) -> int:
        """Copy a set (rules, questions, options) into a new draft with the next seq."""

    @abstractmethod
    async def list_all(self) -> list[tuple[QuizSetInfo, int]]:
        """Every set in any status, with its attempt count."""

    @abstractmethod
    async def get(self, set_id: int) -> QuizSetInfo | None:
        """A set in any status (drafts included), or ``None``."""


class AttemptRepository(ABC):
    """Methods added in Task 5."""
