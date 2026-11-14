"""Attempts: start or resume, autosave, submit, lazy expiry, pause and grading.

A choice question is answered by ticking options and is marked +2/−1/−2 at close. A
subjective one is answered by typing and is marked by the evaluator (ADR 0010): every
attempt started now freezes ``SUBJECTIVE_MARKS`` per subjective question onto itself, the
close adds that to the maximum for each one and records it as blank (0, final) or awaiting,
and ``submit`` asks the evaluation service to mark what awaits. Only ``submit`` ever leads
to a model call; a read that expires an attempt closes it and records its answers as
awaiting, and the next submit of that attempt (or an admin re-run) marks them. An attempt
started before marking existed (``subjective_marks`` ``None``) leaves its written answers
outside its score and maximum, as it always did.

The server clock decides time. Reads expire a due attempt (at ``deadline_at``);
``save`` alone applies the grace window, via ``Attempt.accepts_writes``.

Everything an attempt needs after it starts lives on the attempt and its paper, so
no operation here reads the live set: editing, archiving or deleting a set cannot
change, strand or break an attempt that is already running or finished.

Visibility works the same way. ``include_private`` (true for the set's editors) lets a
private set into the catalogue reads; without it a private set reads as missing, so
nobody else sees it or starts on it. Making a set private refuses only new attempts:
an open one still resumes and submits, and finished results and history stay.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4

from ..clock import Clock
from ..errors import Conflict, Invalid, NotFound
from ..grading import grade
from ..models import (
    AWAITING,
    BLANK,
    CHOICE,
    MAX_TEXT_ANSWER,
    SUBJECTIVE,
    SUBJECTIVE_MARKS,
    Attempt,
    QuestionForSolver,
    QuestionResult,
    QuizSetInfo,
    ReviewQuestion,
    TextMark,
)
from ..ports import AttemptRepository, PaperSource, QuizCatalog
from ..scoring import MARKING, ScoringPolicyFactory
from ..shuffle import display_order
from ..timing import GRACE_MS, TimeLimit


@dataclass(frozen=True)
class AttemptSession:
    attempt: Attempt
    questions: list[QuestionForSolver]
    selections: dict[int, frozenset[int]]
    texts: dict[int, str]
    server_now: int
    created: bool


@dataclass(frozen=True)
class ResultsView:
    attempt: Attempt
    questions: list[ReviewQuestion]
    selections: dict[int, frozenset[int]]
    texts: dict[int, str]
    results: dict[int, QuestionResult]
    marks: dict[int, TextMark]   # subjective questions of a marked attempt; {} otherwise


class AttemptService:
    def __init__(
        self,
        catalog: QuizCatalog,
        papers: PaperSource,
        attempts: AttemptRepository,
        clock: Clock,
        grace_ms: int = GRACE_MS,
        evaluation=None,
    ):
        """``evaluation`` is the ``EvaluationService`` that marks written answers on submit;
        without one (some unit tests) they simply stay awaiting."""
        self._catalog = catalog
        self._papers = papers
        self._attempts = attempts
        self._clock = clock
        self._grace_ms = grace_ms
        self._evaluation = evaluation

    async def start_or_resume(self, email: str, set_id: int, include_private: bool = False) -> AttemptSession:
        now = self._clock.now_ms()
        # An attempt already on this set resumes even if the set has since been
        # archived, deleted or made private: it reads its own paper, never the catalogue.
        attempt = await self._attempts.open_for(set_id, email)
        if attempt is not None and attempt.is_due(now):
            # Its time ran out: hand back the now-expired attempt (the caller shows its results)
            # rather than spend another of max_attempts on a start nobody saw coming.
            await self._expire(attempt)
            attempt = await self._attempts.get(attempt.id)
        if attempt is not None:
            return await self._session(attempt, created=False)

        info = await self._catalog.get_set(set_id, include_private=include_private)
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
            # Every new attempt is marked by the current rule, whatever the set's column says.
            scoring_policy=MARKING,
            reveal_answers=info.reveal_answers,
            started_at=now,
            deadline_at=TimeLimit.of(info.time_limit_minutes).deadline(now),
            finished_at=None,
            status="in_progress",
            score=None,
            max_score=None,
            # Frozen like the scoring policy: a later change of the constant re-marks nothing.
            subjective_marks=SUBJECTIVE_MARKS,
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
        await self._check_answers(attempt_id, {question_id: frozenset(option_ids)}, {})
        await self._attempts.replace_selection(attempt_id, question_id, frozenset(option_ids))

    async def save_text(self, email: str, attempt_id: str, question_id: int, text: str) -> None:
        """Autosave a subjective question's typed answer. Blank text clears it."""
        attempt = await self._owned(email, attempt_id)
        now = self._clock.now_ms()
        if not attempt.accepts_writes(now, self._grace_ms):
            raise Conflict("attempt paused" if attempt.is_paused else "attempt finished")
        await self._check_answers(attempt_id, {}, {question_id: text})
        await self._attempts.replace_text(attempt_id, question_id, _stored_text(text), now)

    async def submit(self, email: str, attempt_id: str, quota_exempt: bool = False) -> Attempt:
        """Close the attempt if it is open, then mark whatever written answers it still has
        awaiting. Safe to repeat: a closed attempt stays closed, and answers already marked
        or held by another request are never sent again. ``quota_exempt`` (admins) skips the
        per-person daily limit."""
        attempt = await self._owned(email, attempt_id)
        if attempt.is_open:
            now = self._clock.now_ms()
            if attempt.is_due(now):
                await self._expire(attempt)
            else:
                await self._finish(attempt, "submitted", now)
            attempt = await self._attempts.get(attempt_id)
        if self._evaluation is not None:
            await self._evaluation.evaluate(attempt, "submit", quota_exempt)
            attempt = await self._attempts.get(attempt_id)
        return attempt

    async def results(self, email: str, attempt_id: str) -> ResultsView:
        attempt = await self._read(email, attempt_id)
        if attempt.is_open:
            raise Conflict("attempt in progress")
        return ResultsView(
            attempt=attempt,
            questions=await self._attempts.review(attempt.id),
            selections=await self._attempts.selections(attempt.id),
            texts=await self._attempts.texts(attempt.id),
            results=await self._attempts.results(attempt.id),
            marks=await self._attempts.text_marks(attempt.id),
        )

    async def pause(
        self,
        email: str,
        attempt_id: str,
        answers: dict[int, frozenset[int]] | None = None,
        texts: dict[int, str] | None = None,
    ) -> AttemptSession:
        """Freeze the clock, storing any answers the browser still held, in one transaction.

        ``answers`` are ticked options and ``texts`` typed answers, each by question id.
        Idempotent; only for an open, timed attempt. The answers and ``paused_at``
        commit together, so a paused attempt can never be missing an answer the
        solver had given.
        """
        attempt = await self._owned(email, attempt_id)
        answers = answers or {}
        texts = texts or {}
        if not attempt.is_open:
            raise Conflict("attempt finished")
        if attempt.deadline_at is None:
            raise Conflict("untimed quiz has no timer to pause")
        if answers or texts:
            await self._check_answers(attempt_id, answers, texts)
        if answers or texts or not attempt.is_paused:
            await self._attempts.pause(
                attempt_id, self._clock.now_ms(), answers,
                {qid: _stored_text(text) for qid, text in texts.items()},
            )
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
        self, email: str, include_private: bool = False
    ) -> tuple[list[QuizSetInfo], dict[int, Attempt], dict[int, Attempt], int]:
        """The published sets the caller may take, their last finished and open attempt per
        set id, and the server time the cards were computed against.

        As in ``intro``, a private set stays for a caller without ``include_private`` while
        they still have an attempt open on it."""
        await self.expire_due_for(email)
        open_ = {a.set_id: a for a in await self._attempts.open_for_user(email)}
        sets = [
            info
            for info in await self._catalog.list_published(include_private=True)
            if include_private or info.visibility == "public" or info.id in open_
        ]
        return (
            sets,
            await self._attempts.last_finished_by_set(email),
            open_,
            self._clock.now_ms(),
        )

    async def intro(
        self, email: str, set_id: int, include_private: bool = False
    ) -> tuple[QuizSetInfo, int, str | None]:
        """A published set, how many attempts the caller has finished on it, and their open one (if any).

        A private set is missing to anyone without ``include_private``, except a caller who
        still has an attempt open on it: their intro stays, so they can resume it."""
        info = await self._catalog.get_set(set_id, include_private=True)
        if info is None:
            raise NotFound("quiz set not found")
        open_attempt = await self._attempts.open_for(set_id, email)
        if open_attempt is not None and open_attempt.is_due(self._clock.now_ms()):
            await self._expire(open_attempt)
            open_attempt = None
        if info.visibility == "private" and not include_private and open_attempt is None:
            raise NotFound("quiz set not found")
        used = await self._attempts.count_finished(set_id, email)
        return info, used, open_attempt.id if open_attempt else None

    async def history(self, email: str) -> tuple[list[Attempt], dict[str, int]]:
        """The person's attempts, newest first, and how many written answers of each still
        await evaluation (absent when none)."""
        await self.expire_due_for(email)
        return await self._attempts.for_user(email), await self._attempts.awaiting_by_attempt(email)

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

    async def _check_answers(
        self, attempt_id: str, answers: dict[int, frozenset[int]], texts: dict[int, str]
    ) -> None:
        """Every question and option must be one this attempt was actually served, and
        each answer must suit its question: options for a choice question, text for a
        subjective one."""
        questions = {q.id: q for q in await self._attempts.paper(attempt_id)}
        for question_id, option_ids in answers.items():
            question = questions.get(question_id)
            if question is None:
                raise Invalid("question is not in this quiz")
            if question.kind != CHOICE:
                raise Invalid("a subjective question takes a text answer, not options")
            if not option_ids <= {o.id for o in question.options}:
                raise Invalid("option is not in this question")
        for question_id, text in texts.items():
            question = questions.get(question_id)
            if question is None:
                raise Invalid("question is not in this quiz")
            if question.kind != SUBJECTIVE:
                raise Invalid("only a subjective question takes a text answer")
            limit = question.max_text_length or MAX_TEXT_ANSWER
            if len(text) > limit:
                raise Invalid(f"this answer is at most {limit:,} characters")

    async def _session(self, attempt: Attempt, created: bool) -> AttemptSession:
        return AttemptSession(
            attempt=attempt,
            questions=await self._attempts.paper(attempt.id),
            selections=await self._attempts.selections(attempt.id),
            texts=await self._attempts.texts(attempt.id),
            server_now=self._clock.now_ms(),
            created=created,
        )

    async def _expire(self, attempt: Attempt) -> None:
        await self._finish(attempt, "expired", attempt.deadline_at)

    async def _finish(self, attempt: Attempt, status: str, finished_at: int) -> None:
        # The key holds choice questions only, so the grader never sees a subjective one and
        # every choice score is exactly what it was before written answers were marked.
        graded = grade(
            await self._attempts.answer_key(attempt.id),
            await self._attempts.selections(attempt.id),
            ScoringPolicyFactory.for_name(attempt.scoring_policy),
        )
        marks: tuple[tuple[int, str, float], ...] = ()
        if attempt.subjective_marks is not None:
            # Each subjective question adds its marks to the maximum. A blank one is 0 and
            # final; a typed one awaits the evaluator and counts nothing until marked.
            typed = await self._attempts.texts(attempt.id)
            subjective = [q.id for q in await self._attempts.paper(attempt.id) if q.kind == SUBJECTIVE]
            marks = tuple(
                (qid, AWAITING if qid in typed else BLANK, attempt.subjective_marks) for qid in subjective
            )
            graded = replace(graded, max_score=graded.max_score + attempt.subjective_marks * len(subjective))
        await self._attempts.finish(attempt.id, status, finished_at, graded, marks)


def _stored_text(text: str) -> str | None:
    """What to store for a typed answer: the text exactly as typed, or ``None`` (blank)
    when it holds nothing but whitespace."""
    return text if text.strip() else None
