"""Frozen domain dataclasses and the derived set name."""

from __future__ import annotations

from dataclasses import dataclass


def set_name(
    subtopic_name: str | None,
    difficulty: str | None,
    style: str,
    seq: int,
    title: str | None,
    include_subtopic: bool = True,
) -> str:
    """``[subtopic] · [Easy|Medium|Hard] · [Scenario] · Set {seq}``.

    A non-null ``title`` replaces the whole derived name.
    """
    if title is not None:
        return title
    parts: list[str] = []
    if include_subtopic and subtopic_name:
        parts.append(subtopic_name)
    if difficulty:
        parts.append(difficulty.capitalize())
    if style == "scenario":
        parts.append("Scenario")
    parts.append(f"Set {seq}")
    return " · ".join(parts)


@dataclass(frozen=True)
class User:
    email: str
    display_name: str | None
    role: str


@dataclass(frozen=True)
class QuizSetInfo:
    id: int
    topic_id: int
    topic_name: str
    topic_position: int
    subtopic_id: int | None
    subtopic_name: str | None
    subtopic_position: int | None
    difficulty: str | None
    style: str
    seq: int
    title: str | None
    description: str | None
    status: str
    time_limit_minutes: int | None
    scoring_policy: str
    shuffle_questions: bool
    shuffle_options: bool
    reveal_answers: bool
    max_attempts: int | None
    question_count: int

    @property
    def name(self) -> str:
        return set_name(self.subtopic_name, self.difficulty, self.style, self.seq, self.title)

    @property
    def short_name(self) -> str:
        return set_name(
            self.subtopic_name, self.difficulty, self.style, self.seq, self.title,
            include_subtopic=False,
        )


@dataclass(frozen=True)
class OptionForSolver:
    id: int
    body: str


@dataclass(frozen=True)
class QuestionForSolver:
    id: int
    prompt: str
    options: tuple[OptionForSolver, ...]


@dataclass(frozen=True)
class QuestionKey:
    question_id: int
    points: float
    correct: frozenset[int]


@dataclass(frozen=True)
class ReviewOption:
    id: int
    body: str
    is_correct: bool


@dataclass(frozen=True)
class ReviewQuestion:
    id: int
    prompt: str
    explanation: str | None
    points: float
    options: tuple[ReviewOption, ...]


@dataclass(frozen=True)
class Attempt:
    id: str
    set_id: int
    user_email: str
    started_at: int
    deadline_at: int | None
    finished_at: int | None
    status: str
    score: float | None
    max_score: float | None

    @property
    def is_open(self) -> bool:
        return self.status == "in_progress"

    def is_due(self, now_ms: int) -> bool:
        return self.deadline_at is not None and now_ms >= self.deadline_at

    def accepts_writes(self, now_ms: int, grace_ms: int) -> bool:
        return self.is_open and (
            self.deadline_at is None or now_ms <= self.deadline_at + grace_ms
        )


@dataclass(frozen=True)
class QuestionResult:
    question_id: int
    awarded_points: float
    is_correct: bool


@dataclass(frozen=True)
class GradeResult:
    score: float
    max_score: float
    results: tuple[QuestionResult, ...]
