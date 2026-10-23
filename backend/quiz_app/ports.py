"""Ports: what the services need from storage. D1 implements them (``quiz_app.d1``)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    Attempt,
    GradeResult,
    QuestionForSolver,
    QuestionKey,
    QuestionResult,
    QuizSetInfo,
    ReviewQuestion,
    User,
)
from .validation import QuestionImport, SetImport


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
    async def set_for_attempt(self, set_id: int) -> QuizSetInfo | None:
        """A set in any status, for an attempt already started on it; ``None`` only if no such id."""

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

    @abstractmethod
    async def delete(self, set_id: int) -> None:
        """Hard-delete a set (questions/options cascade). Raises Conflict if it has attempts."""

    @abstractmethod
    async def update(self, set_id: int, imp: SetImport, now_ms: int) -> None:
        """Replace the set's mutable props and its questions/options, in place. Raises
        Conflict when the set has attempts (replacing questions would orphan them)."""

    @abstractmethod
    async def questions(self, set_id: int) -> list[QuestionImport]:
        """The set's questions with correctness, for the editor."""


class AttemptRepository(ABC):
    @abstractmethod
    async def create(self, attempt: Attempt) -> Attempt:
        """Insert an open attempt. If the person already has one open for the set
        (``uq_attempts_one_open``), return that one instead."""

    @abstractmethod
    async def get(self, attempt_id: str) -> Attempt | None: ...

    @abstractmethod
    async def open_for(self, set_id: int, email: str) -> Attempt | None: ...

    @abstractmethod
    async def count_finished(self, set_id: int, email: str) -> int: ...

    @abstractmethod
    async def selections(self, attempt_id: str) -> dict[int, frozenset[int]]: ...

    @abstractmethod
    async def replace_selection(self, attempt_id: str, question_id: int, option_ids: frozenset[int]) -> None:
        """One batch: delete the question's rows, then insert the new ones."""

    @abstractmethod
    async def finish(self, attempt_id: str, status: str, finished_at: int, grade: GradeResult) -> bool:
        """Close an open attempt and write its results once. False if it was already closed."""

    @abstractmethod
    async def pause(self, attempt_id: str, paused_at: int) -> None:
        """Freeze the clock: set paused_at on an open attempt."""

    @abstractmethod
    async def resume(self, attempt_id: str, now_ms: int) -> None:
        """Extend deadline_at by the paused duration and clear paused_at."""

    @abstractmethod
    async def results(self, attempt_id: str) -> dict[int, QuestionResult]: ...

    @abstractmethod
    async def for_user(self, email: str) -> list[Attempt]:
        """Newest first."""

    @abstractmethod
    async def open_for_user(self, email: str) -> list[Attempt]: ...

    @abstractmethod
    async def last_finished_by_set(self, email: str) -> dict[int, Attempt]: ...
