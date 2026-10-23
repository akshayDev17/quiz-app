"""Attempts: start or resume, autosave, submit, lazy expiry and grading.

The server clock decides time. Reads expire a due attempt (at ``deadline_at``);
``save`` alone applies the grace window, via ``Attempt.accepts_writes``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from uuid import uuid4

from ..clock import Clock
from ..errors import Conflict, Invalid, NotFound
from ..grading import grade
from ..models import (
    Attempt,
    QuestionForSolver,
    QuestionResult,
    QuizSetInfo,
    ReviewQuestion,
)
from ..ports import AnswerKeyReader, AttemptRepository, QuizCatalog
from ..scoring import ScoringPolicyFactory
from ..shuffle import display_order
from ..timing import GRACE_MS, TimeLimit


@dataclass(frozen=True)
class AttemptSession:
    attempt: Attempt
    set: QuizSetInfo
    questions: list[QuestionForSolver]
    selections: dict[int, frozenset[int]]
    server_now: int
    created: bool


@dataclass(frozen=True)
class ResultsView:
    attempt: Attempt
    set: QuizSetInfo
    questions: list[ReviewQuestion]
    selections: dict[int, frozenset[int]]
    results: dict[int, QuestionResult]


def review_in_display_order(
    attempt: Attempt,
    info: QuizSetInfo,
    solver: list[QuestionForSolver],
    review: list[ReviewQuestion],
) -> list[ReviewQuestion]:
    """The review questions, permuted exactly as the solver saw them (questions and options)."""
    by_id = {q.id: q for q in review}
    out = []
    for shown in display_order(attempt.id, solver, info.shuffle_questions, info.shuffle_options):
        question = by_id[shown.id]
        options = {o.id: o for o in question.options}
        out.append(dataclasses.replace(question, options=tuple(options[o.id] for o in shown.options)))
    return out


class AttemptService:
    def __init__(
        self,
        catalog: QuizCatalog,
        keys: AnswerKeyReader,
        attempts: AttemptRepository,
        clock: Clock,
        grace_ms: int = GRACE_MS,
    ):
        self._catalog = catalog
        self._keys = keys
        self._attempts = attempts
        self._clock = clock
        self._grace_ms = grace_ms

    async def start_or_resume(self, email: str, set_id: int) -> AttemptSession:
        info = await self._catalog.get_set(set_id)
        if info is None:
            raise NotFound("quiz set not found")
        now = self._clock.now_ms()
        attempt = await self._attempts.open_for(set_id, email)
        if attempt is not None and attempt.is_due(now):
            await self._expire(attempt, info)
            attempt = None
        if attempt is not None:
            return await self._session(attempt, info, created=False)
        if info.max_attempts is not None and await self._attempts.count_finished(set_id, email) >= info.max_attempts:
            raise Conflict("no attempts left")
        new = Attempt(
            id=uuid4().hex,
            set_id=set_id,
            user_email=email,
            started_at=now,
            deadline_at=TimeLimit.of(info.time_limit_minutes).deadline(now),
            finished_at=None,
            status="in_progress",
            score=None,
            max_score=None,
        )
        attempt = await self._attempts.create(new)
        return await self._session(attempt, info, created=attempt.id == new.id)

    async def session(self, email: str, attempt_id: str) -> AttemptSession:
        attempt, info = await self._read(email, attempt_id)
        return await self._session(attempt, info, created=False)

    async def save(self, email: str, attempt_id: str, question_id: int, option_ids: list[int]) -> None:
        attempt = await self._owned(email, attempt_id)
        if not attempt.accepts_writes(self._clock.now_ms(), self._grace_ms):
            raise Conflict("attempt finished")
        questions = {q.id: q for q in await self._catalog.questions_for_solver(attempt.set_id)}
        question = questions.get(question_id)
        if question is None:
            raise Invalid("question is not in this quiz")
        picked = frozenset(option_ids)
        if not picked <= {o.id for o in question.options}:
            raise Invalid("option is not in this question")
        await self._attempts.replace_selection(attempt_id, question_id, picked)

    async def submit(self, email: str, attempt_id: str) -> Attempt:
        attempt = await self._owned(email, attempt_id)
        if not attempt.is_open:
            return attempt
        info = await self._set_for(attempt)
        now = self._clock.now_ms()
        if attempt.is_due(now):
            await self._expire(attempt, info)
        else:
            await self._finish(attempt, info, "submitted", now)
        return await self._attempts.get(attempt_id)

    async def results(self, email: str, attempt_id: str) -> ResultsView:
        attempt, info = await self._read(email, attempt_id)
        if attempt.is_open:
            raise Conflict("attempt in progress")
        questions = review_in_display_order(
            attempt,
            info,
            await self._catalog.questions_for_solver(attempt.set_id),
            await self._keys.review_questions(attempt.set_id),
        )
        return ResultsView(
            attempt=attempt,
            set=info,
            questions=questions,
            selections=await self._attempts.selections(attempt.id),
            results=await self._attempts.results(attempt.id),
        )

    async def expire_due_for(self, email: str) -> None:
        now = self._clock.now_ms()
        for attempt in await self._attempts.open_for_user(email):
            if attempt.is_due(now):
                await self._expire(attempt, await self._set_for(attempt))

    async def overview(
        self, email: str
    ) -> tuple[list[QuizSetInfo], dict[int, Attempt], dict[int, Attempt]]:
        """The published sets, plus the caller's last finished and open attempt per set id."""
        await self.expire_due_for(email)
        return (
            await self._catalog.list_published(),
            await self._attempts.last_finished_by_set(email),
            {a.set_id: a for a in await self._attempts.open_for_user(email)},
        )

    async def intro(self, email: str, set_id: int) -> tuple[QuizSetInfo, int, str | None]:
        """A published set, how many attempts the caller has finished on it, and their open one (if any)."""
        info = await self._catalog.get_set(set_id)
        if info is None:
            raise NotFound("quiz set not found")
        open_attempt = await self._attempts.open_for(set_id, email)
        if open_attempt is not None and open_attempt.is_due(self._clock.now_ms()):
            await self._expire(open_attempt, info)
            open_attempt = None
        used = await self._attempts.count_finished(set_id, email)
        return info, used, open_attempt.id if open_attempt else None

    async def history(self, email: str) -> list[tuple[Attempt, QuizSetInfo]]:
        await self.expire_due_for(email)
        sets: dict[int, QuizSetInfo] = {}
        out = []
        for attempt in await self._attempts.for_user(email):
            if attempt.set_id not in sets:
                sets[attempt.set_id] = await self._set_for(attempt)
            out.append((attempt, sets[attempt.set_id]))
        return out

    async def _owned(self, email: str, attempt_id: str) -> Attempt:
        """The caller's attempt; anyone else's is indistinguishable from a missing one."""
        attempt = await self._attempts.get(attempt_id)
        if attempt is None or attempt.user_email != email:
            raise NotFound("attempt not found")
        return attempt

    async def _read(self, email: str, attempt_id: str) -> tuple[Attempt, QuizSetInfo]:
        """The caller's attempt and its set, expired first if it is due."""
        attempt = await self._owned(email, attempt_id)
        info = await self._set_for(attempt)
        if attempt.is_open and attempt.is_due(self._clock.now_ms()):
            await self._expire(attempt, info)
            attempt = await self._attempts.get(attempt_id)
        return attempt, info

    async def _set_for(self, attempt: Attempt) -> QuizSetInfo:
        """The attempt's set in any status: archiving never strands or hides an attempt."""
        info = await self._catalog.set_for_attempt(attempt.set_id)
        if info is None:
            raise NotFound("quiz set not found")
        return info

    async def _session(self, attempt: Attempt, info: QuizSetInfo, created: bool) -> AttemptSession:
        questions = await self._catalog.questions_for_solver(attempt.set_id)
        return AttemptSession(
            attempt=attempt,
            set=info,
            questions=display_order(attempt.id, questions, info.shuffle_questions, info.shuffle_options),
            selections=await self._attempts.selections(attempt.id),
            server_now=self._clock.now_ms(),
            created=created,
        )

    async def _expire(self, attempt: Attempt, info: QuizSetInfo) -> None:
        await self._finish(attempt, info, "expired", attempt.deadline_at)

    async def _finish(self, attempt: Attempt, info: QuizSetInfo, status: str, finished_at: int) -> None:
        graded = grade(
            await self._keys.answer_key(attempt.set_id),
            await self._attempts.selections(attempt.id),
            ScoringPolicyFactory.for_name(info.scoring_policy),
        )
        await self._attempts.finish(attempt.id, status, finished_at, graded)
