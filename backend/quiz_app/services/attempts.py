"""Attempts: start or resume, autosave, submit, lazy expiry, pause and grading.

The server clock decides time. Reads expire a due attempt (at ``deadline_at``);
``save`` alone applies the grace window, via ``Attempt.accepts_writes``.

Everything an attempt needs after it starts lives on the attempt and its paper, so
no operation here reads the live set: editing, archiving or deleting a set cannot
change, strand or break an attempt that is already running or finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from ..clock import Clock
from ..errors import Conflict, Invalid, NotFound
from ..grading import grade
from ..models import Attempt, QuestionForSolver, QuestionResult, QuizSetInfo, ReviewQuestion
from ..ports import AttemptRepository, PaperSource, QuizCatalog
from ..scoring import ScoringPolicyFactory
from ..shuffle import display_order
from ..timing import GRACE_MS, TimeLimit


@dataclass(frozen=True)
class AttemptSession:
    attempt: Attempt
    questions: list[QuestionForSolver]
    selections: dict[int, frozenset[int]]
    server_now: int
    created: bool


@dataclass(frozen=True)
class ResultsView:
    attempt: Attempt
    questions: list[ReviewQuestion]
    selections: dict[int, frozenset[int]]
    results: dict[int, QuestionResult]


class AttemptService:
    def __init__(
        self,
        catalog: QuizCatalog,
        papers: PaperSource,
        attempts: AttemptRepository,
        clock: Clock,
        grace_ms: int = GRACE_MS,
    ):
        self._catalog = catalog
        self._papers = papers
        self._attempts = attempts
        self._clock = clock
        self._grace_ms = grace_ms

    async def start_or_resume(self, email: str, set_id: int) -> AttemptSession:
        now = self._clock.now_ms()
        # An attempt already on this set resumes even if the set has since been
        # archived or deleted: it reads its own paper, never the catalogue.
        attempt = await self._attempts.open_for(set_id, email)
        if attempt is not None and attempt.is_due(now):
            # Its time ran out: hand back the now-expired attempt (the caller shows its results)
            # rather than spend another of max_attempts on a start nobody saw coming.
            await self._expire(attempt)
            attempt = await self._attempts.get(attempt.id)
        if attempt is not None:
            return await self._session(attempt, created=False)

        info = await self._catalog.get_set(set_id)
        if info is None:
            raise NotFound("quiz set not found")
        if info.max_attempts is not None and await self._attempts.count_finished(
            set_id, email
        ) >= info.max_attempts:
            raise Conflict("no attempts left")

        new = Attempt(
            id=uuid4().hex,
            set_id=set_id,
            user_email=email,
            topic_name=info.topic_name,
            subtopic_name=info.subtopic_name,
            difficulty=info.difficulty,
            style=info.style,
            seq=info.seq,
            title=info.title,
            scoring_policy=info.scoring_policy,
            reveal_answers=info.reveal_answers,
            started_at=now,
            deadline_at=TimeLimit.of(info.time_limit_minutes).deadline(now),
            finished_at=None,
            status="in_progress",
            score=None,
            max_score=None,
        )
        # The paper is written in the order this attempt will be served, so display
        # order is decided once, here, and never re-derived.
        paper = display_order(
            new.id,
            await self._papers.paper_source(set_id),
            info.shuffle_questions,
            info.shuffle_options,
        )
        attempt = await self._attempts.create(new, paper)
        return await self._session(attempt, created=attempt.id == new.id)

    async def session(self, email: str, attempt_id: str) -> AttemptSession:
        return await self._session(await self._read(email, attempt_id), created=False)

    async def save(self, email: str, attempt_id: str, question_id: int, option_ids: list[int]) -> None:
        attempt = await self._owned(email, attempt_id)
        if not attempt.accepts_writes(self._clock.now_ms(), self._grace_ms):
            raise Conflict("attempt paused" if attempt.is_paused else "attempt finished")
        await self._check_answers(attempt_id, {question_id: frozenset(option_ids)})
        await self._attempts.replace_selection(attempt_id, question_id, frozenset(option_ids))

    async def submit(self, email: str, attempt_id: str) -> Attempt:
        attempt = await self._owned(email, attempt_id)
        if not attempt.is_open:
            return attempt
        now = self._clock.now_ms()
        if attempt.is_due(now):
            await self._expire(attempt)
        else:
            await self._finish(attempt, "submitted", now)
        return await self._attempts.get(attempt_id)

    async def results(self, email: str, attempt_id: str) -> ResultsView:
        attempt = await self._read(email, attempt_id)
        if attempt.is_open:
            raise Conflict("attempt in progress")
        return ResultsView(
            attempt=attempt,
            questions=await self._attempts.review(attempt.id),
            selections=await self._attempts.selections(attempt.id),
            results=await self._attempts.results(attempt.id),
        )

    async def pause(
        self,
        email: str,
        attempt_id: str,
        answers: dict[int, frozenset[int]] | None = None,
    ) -> AttemptSession:
        """Freeze the clock, storing any answers the browser still held, in one transaction.

        Idempotent; only for an open, timed attempt. The answers and ``paused_at``
        commit together, so a paused attempt can never be missing an answer the
        solver had given.
        """
        attempt = await self._owned(email, attempt_id)
        answers = answers or {}
        if not attempt.is_open:
            raise Conflict("attempt finished")
        if attempt.deadline_at is None:
            raise Conflict("untimed quiz has no timer to pause")
        if answers:
            await self._check_answers(attempt_id, answers)
        if answers or not attempt.is_paused:
            await self._attempts.pause(attempt_id, self._clock.now_ms(), answers)
        return await self._session(await self._owned(email, attempt_id), created=False)

    async def resume(self, email: str, attempt_id: str) -> AttemptSession:
        """Extend the deadline by the paused duration and unfreeze. Idempotent."""
        attempt = await self._owned(email, attempt_id)
        if not attempt.is_open:
            raise Conflict("attempt finished")
        if attempt.is_paused:
            await self._attempts.resume(attempt_id, self._clock.now_ms())
        return await self._session(await self._owned(email, attempt_id), created=False)

    async def expire_due_for(self, email: str) -> None:
        now = self._clock.now_ms()
        for attempt in await self._attempts.open_for_user(email):
            if attempt.is_due(now):
                await self._expire(attempt)

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
            await self._expire(open_attempt)
            open_attempt = None
        used = await self._attempts.count_finished(set_id, email)
        return info, used, open_attempt.id if open_attempt else None

    async def history(self, email: str) -> list[Attempt]:
        await self.expire_due_for(email)
        return await self._attempts.for_user(email)

    async def _owned(self, email: str, attempt_id: str) -> Attempt:
        """The caller's attempt; anyone else's is indistinguishable from a missing one."""
        attempt = await self._attempts.get(attempt_id)
        if attempt is None or attempt.user_email != email:
            raise NotFound("attempt not found")
        return attempt

    async def _read(self, email: str, attempt_id: str) -> Attempt:
        """The caller's attempt, expired first if it is due."""
        attempt = await self._owned(email, attempt_id)
        if attempt.is_open and attempt.is_due(self._clock.now_ms()):
            await self._expire(attempt)
            attempt = await self._attempts.get(attempt_id)
        return attempt

    async def _check_answers(self, attempt_id: str, answers: dict[int, frozenset[int]]) -> None:
        """Every question and option must be one this attempt was actually served."""
        questions = {q.id: q for q in await self._attempts.paper(attempt_id)}
        for question_id, option_ids in answers.items():
            question = questions.get(question_id)
            if question is None:
                raise Invalid("question is not in this quiz")
            if not option_ids <= {o.id for o in question.options}:
                raise Invalid("option is not in this question")

    async def _session(self, attempt: Attempt, created: bool) -> AttemptSession:
        return AttemptSession(
            attempt=attempt,
            questions=await self._attempts.paper(attempt.id),
            selections=await self._attempts.selections(attempt.id),
            server_now=self._clock.now_ms(),
            created=created,
        )

    async def _expire(self, attempt: Attempt) -> None:
        await self._finish(attempt, "expired", attempt.deadline_at)

    async def _finish(self, attempt: Attempt, status: str, finished_at: int) -> None:
        graded = grade(
            await self._attempts.answer_key(attempt.id),
            await self._attempts.selections(attempt.id),
            ScoringPolicyFactory.for_name(attempt.scoring_policy),
        )
        await self._attempts.finish(attempt.id, status, finished_at, graded)
