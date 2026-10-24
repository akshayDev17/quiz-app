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
    """An attempt and the quiz as it was when the attempt started.

    The name ingredients and the grading policy are copied at start, not read live:
    renaming, editing, archiving or deleting the set must never rewrite an attempt.
    ``set_id`` is ``None`` once the set has been deleted; everything needed to show
    and regrade the attempt is already here and in its paper.
    """

    id: str
    set_id: int | None
    user_email: str
    topic_name: str
    subtopic_name: str | None
    difficulty: str | None
    style: str
    seq: int
    title: str | None
    scoring_policy: str
    reveal_answers: bool
    started_at: int
    deadline_at: int | None
    finished_at: int | None
    status: str
    score: float | None
    max_score: float | None
    paused_at: int | None = None

    @property
    def name(self) -> str:
        """The set's name as it was when this attempt started."""
        return set_name(self.subtopic_name, self.difficulty, self.style, self.seq, self.title)

    @property
    def is_open(self) -> bool:
        return self.status == "in_progress"

    @property
    def is_paused(self) -> bool:
        return self.paused_at is not None

    def is_due(self, now_ms: int) -> bool:
        # A paused attempt's clock is frozen, so it is never due.
        return self.deadline_at is not None and self.paused_at is None and now_ms >= self.deadline_at

    def accepts_writes(self, now_ms: int, grace_ms: int) -> bool:
        # No writes while paused: the solver resumes before answering again.
        return self.is_open and self.paused_at is None and (
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
