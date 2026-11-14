"""Wire shapes: one function per type in the wire contract (snake_case keys, epoch-ms times).

Solver-facing serializers read only from solver-facing models, so no attempt payload
carries an answer while that attempt is open. Answers are exposed in two places only:
``results``, reachable only for a finished attempt, and ``public_set``, the View of a
published set. Both follow the set's ``reveal_answers``. ``public_set`` takes no caller,
so by owner decision a published set with ``reveal_answers`` true exposes its key to
anyone, including a solver whose attempt on that set is still open.

Which provider or model marked a written answer, and anything about budgets, prices or
spend, appear only in ``admin_evaluators``. A solver's results say an answer was marked by
the AI evaluator and show its marks and feedback, nothing more.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import AWAITING, MARKED, SUBJECTIVE, Attempt, QuestionResult, QuizSetInfo, ReviewQuestion, TextMark, User
from .scoring import ScoringPolicyFactory
from .services.attempts import AttemptSession, ResultsView
from .keycipher import MASTER_KEY_SECRET
from .services.evaluator_admin import EvaluatorsOverview
from .validation import QuestionImport


def me(user: User) -> dict:
    return {"email": user.email, "display_name": user.display_name, "role": user.role}


def _public_card(info: QuizSetInfo) -> dict:
    """A set's card as anyone may see it: what the set is, nothing about who took it."""
    return {
        "id": info.id,
        "name": info.name,
        "short_name": info.short_name,
        "difficulty": info.difficulty,
        "style": info.style,
        "time_limit_minutes": info.time_limit_minutes,
        "question_count": info.question_count,
    }


def _card(
    info: QuizSetInfo, last: Attempt | None, open_attempt: Attempt | None, now_ms: int
) -> dict:
    return {
        **_public_card(info),
        "last": None if last is None else {
            "attempt_id": last.id,
            "status": last.status,
            "score": last.score,
            "max_score": last.max_score,
        },
        "open_attempt": None if open_attempt is None else {
            "attempt_id": open_attempt.id,
            # Server-computed, pause already folded in: the browser cannot reproduce
            # this from a deadline alone, and got it wrong for paused attempts.
            "remaining_ms": open_attempt.remaining_ms(now_ms),
        },
    }


def topics(
    sets: list[QuizSetInfo], last: dict[int, Attempt], open_: dict[int, Attempt], now_ms: int
) -> dict:
    return _grouped(sets, lambda info: _card(info, last.get(info.id), open_.get(info.id), now_ms))


def public_topics(sets: list[QuizSetInfo]) -> dict:
    """``topics`` for a signed-out visitor: the same grouping, cards without ``last`` or ``open_attempt``."""
    return _grouped(sets, _public_card)


def _grouped(sets: list[QuizSetInfo], card: Callable[[QuizSetInfo], dict]) -> dict:
    """Topics by position then id; in each, the whole-topic group first, then subtopics by position."""
    by_topic: dict[int, tuple[QuizSetInfo, list[QuizSetInfo]]] = {}
    for info in sets:
        by_topic.setdefault(info.topic_id, (info, []))[1].append(info)

    out = []
    for first, members in sorted(by_topic.values(), key=lambda t: (t[0].topic_position, t[0].topic_id)):
        by_group: dict[int | None, list[QuizSetInfo]] = {}
        for info in members:
            by_group.setdefault(info.subtopic_id, []).append(info)
        ordered = sorted(
            by_group.values(),
            key=lambda g: (g[0].subtopic_id is not None, g[0].subtopic_position or 0, g[0].subtopic_id or 0),
        )
        out.append({
            "id": first.topic_id,
            "name": first.topic_name,
            "groups": [
                {
                    "subtopic": None if g[0].subtopic_id is None
                    else {"id": g[0].subtopic_id, "name": g[0].subtopic_name},
                    "sets": [card(i) for i in g],
                }
                for g in ordered
            ],
        })
    return {"topics": out}


def set_intro(info: QuizSetInfo, attempts_used: int, open_attempt_id: str | None) -> dict:
    return {
        "id": info.id,
        "topic": info.topic_name,
        "subtopic": info.subtopic_name,
        "name": info.name,
        "description": info.description,
        "time_limit_minutes": info.time_limit_minutes,
        "question_count": info.question_count,
        "subjective_count": info.subjective_count,
        "max_attempts": info.max_attempts,
        "attempts_used": attempts_used,
        "open_attempt_id": open_attempt_id,
    }


def attempt_session(session: AttemptSession) -> dict:
    attempt = session.attempt
    return {
        "attempt": {
            "id": attempt.id,
            "set_id": attempt.set_id,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "deadline_at": attempt.deadline_at,
            "paused_at": attempt.paused_at,
        },
        "server_now": session.server_now,
        # The name the attempt started under, not the set's current one.
        "set": {"name": attempt.name, "topic": attempt.topic_name, "subtopic": attempt.subtopic_name},
        "questions": [
            {
                "id": q.id,
                "kind": q.kind,
                "prompt": q.prompt,
                "options": [{"id": o.id, "body": o.body} for o in q.options],  # [] for subjective
                # The most characters a written answer may hold (null for choice): the server's
                # limit, which the page's text box mirrors.
                "max_text_length": q.max_text_length,
            }
            for q in session.questions
        ],
        "selections": {str(qid): sorted(ids) for qid, ids in session.selections.items()},
        # What the solver typed, per subjective question; a blank one has no entry.
        "texts": {str(qid): body for qid, body in session.texts.items()},
    }


def results(view: ResultsView) -> dict:
    attempt = view.attempt
    # Pinned at start: flipping reveal_answers later cannot expose an old attempt's key.
    reveal = attempt.reveal_answers
    policy = ScoringPolicyFactory.for_name(attempt.scoring_policy)
    questions = []
    for q in view.questions:
        if q.kind == SUBJECTIVE:
            mark = view.marks.get(q.id) if attempt.subjective_marks is not None else None
            questions.append(_subjective_result(q, view.texts.get(q.id), reveal, mark))
            continue
        # Defensive: a missing result row reads as unanswered rather than failing the page.
        graded = view.results.get(q.id) or QuestionResult(q.id, 0, False)
        picked = view.selections.get(q.id, frozenset())
        correct = frozenset(o.id for o in q.options if o.is_correct)
        questions.append({
            "id": q.id,
            "kind": q.kind,
            "prompt": q.prompt,
            "points": policy.max_award(q.points, correct),
            "awarded_points": graded.awarded_points,
            "is_correct": graded.is_correct,
            "explanation": q.explanation if reveal else None,
            "options": [
                {"id": o.id, "body": o.body, "selected": o.id in picked, "correct": o.is_correct if reveal else None}
                for o in q.options
            ],
        })
    return {
        "attempt": {
            "id": attempt.id,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "finished_at": attempt.finished_at,
            "score": attempt.score,
            "max_score": attempt.max_score,
            # Written answers still waiting for the evaluator: the score is provisional
            # until this is 0, and each of them adds to it when marked.
            "awaiting_count": sum(1 for m in view.marks.values() if m.status == AWAITING),
        },
        "set": {
            "id": attempt.set_id,          # None once the set has been deleted
            "name": attempt.name,
            "topic": attempt.topic_name,
            "scoring_policy": attempt.scoring_policy,
            "reveal_answers": reveal,
        },
        "questions": questions,
    }


def _subjective_result(q: ReviewQuestion, text: str | None, reveal: bool, mark: TextMark | None) -> dict:
    """A subjective question on the results page.

    ``evaluation`` is ``blank`` (0), ``awaiting`` (nothing counted yet, so no
    ``awarded_points``), ``marked`` (the evaluator's marks and feedback) or ``flagged``
    (0, flagged for review), out of ``points``; ``None`` with no points at all for an
    attempt started before written answers were marked. Never who or what marked it.

    The solver always sees what they typed (``None`` when they left it blank); the model
    answer follows ``reveal_answers``, like the explanation."""
    return {
        "id": q.id,
        "kind": q.kind,
        "prompt": q.prompt,
        "points": mark.max_marks if mark else None,
        "awarded_points": None if mark is None or mark.status == AWAITING else mark.awarded,
        "is_correct": None,
        "explanation": q.explanation if reveal else None,
        "options": [],
        "text_answer": text,
        "model_answer": q.model_answer if reveal else None,
        "evaluation": mark.status if mark else None,
        "feedback": mark.feedback if mark and mark.status == MARKED else None,
    }


def history(attempts: list[Attempt], awaiting: dict[str, int] | None = None) -> dict:
    awaiting = awaiting or {}
    return {
        "attempts": [
            {
                "id": a.id,
                "set_id": a.set_id,            # None once the set has been deleted
                "name": a.name,               # as it was when this attempt started
                "topic": a.topic_name,
                "status": a.status,
                "started_at": a.started_at,
                "finished_at": a.finished_at,
                "score": None if a.is_open else a.score,
                "max_score": None if a.is_open else a.max_score,
                # Written answers still awaiting the evaluator: the score is provisional.
                "awaiting_count": awaiting.get(a.id, 0),
            }
            for a in attempts
        ]
    }


def admin_sets(rows: list[tuple[QuizSetInfo, int]]) -> dict:
    return {
        "sets": [
            {
                "id": info.id,
                "topic": info.topic_name,
                "name": info.name,
                "status": info.status,
                "visibility": info.visibility,
                "question_count": info.question_count,
                "attempt_count": attempt_count,
            }
            for info, attempt_count in rows
        ]
    }


def admin_set_detail(info: QuizSetInfo, questions: list[QuestionImport]) -> dict:
    """Everything the editor needs: set props plus questions with their answer key."""
    return {
        "id": info.id,
        "name": info.name,
        "topic": info.topic_name,
        "subtopic": info.subtopic_name,
        "status": info.status,
        "seq": info.seq,
        "question_count": info.question_count,
        "difficulty": info.difficulty,
        "style": info.style,
        "title": info.title,
        "description": info.description,
        "time_limit_minutes": info.time_limit_minutes,
        "scoring_policy": info.scoring_policy,
        "max_attempts": info.max_attempts,
        "shuffle_questions": info.shuffle_questions,
        "shuffle_options": info.shuffle_options,
        "reveal_answers": info.reveal_answers,
        "visibility": info.visibility,
        "questions": [_admin_question(q) for q in questions],
    }


def _admin_question(q: QuestionImport) -> dict:
    """A question in its import shape, so the editor can send it straight back."""
    if q.kind == SUBJECTIVE:
        return {
            "type": q.kind,
            "prompt": q.prompt,
            "explanation": q.explanation,
            "model_answer": q.model_answer,
            # Only when authored, so a question without them round-trips unchanged.
            **({"key_points": list(q.key_points)} if q.key_points else {}),
        }
    return {
        "type": q.kind,
        "prompt": q.prompt,
        "explanation": q.explanation,
        "points": q.points,
        "options": [{"body": body, "correct": correct} for body, correct in q.options],
    }


def public_set(info: QuizSetInfo, questions: list[ReviewQuestion]) -> dict:
    """A published set for the signed-out View: questions with the answer key, never a score.

    The key, explanations and model answers follow the set's ``reveal_answers``: View shows what a solver
    sees after finishing, to anyone at any time, open attempt or not. No points: View has
    nothing to mark."""
    reveal = info.reveal_answers
    return {
        "set": {
            "id": info.id,
            "name": info.name,
            "topic": info.topic_name,
            "subtopic": info.subtopic_name,
            "description": info.description,
            "time_limit_minutes": info.time_limit_minutes,
            "question_count": info.question_count,
            "reveal_answers": reveal,
        },
        "questions": [
            {
                "id": q.id,
                "kind": q.kind,
                "prompt": q.prompt,
                "explanation": q.explanation if reveal else None,
                "model_answer": q.model_answer if reveal else None,
                "options": [
                    {"id": o.id, "body": o.body, "correct": o.is_correct if reveal else None}
                    for o in q.options
                ],
            }
            for q in questions
        ],
    }


def _usd(micros: int) -> float:
    return round(micros / 1_000_000, 6)


def _balance(balance, at) -> dict | None:
    if balance is None:
        return None
    return {
        "limit": _usd(balance.limit_micros), "spent": _usd(balance.spent_micros),
        "remaining": _usd(balance.remaining_micros), "currency": balance.currency,
        "source": balance.source, "as_of": at,
    }


def admin_evaluators(o: EvaluatorsOverview) -> dict:
    """The admin's evaluator page. A key appears as its provider, label, last four
    characters, non-secret settings and status: never a key value, a sealed value, or a
    billing secret. ``spent_usd`` is the app's own tracking for ``month`` (UTC), not the
    provider's bill; ``provider_budget`` is the provider's own reading, where it has one."""
    return {
        "month": o.month,
        "key_storage": {"ready": o.key_storage_ready, "secret": MASTER_KEY_SECRET},
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "key_fields": [f.describe() for f in p.key_fields],
                "billing": (
                    {"label": p.billing_label, "fields": [f.describe() for f in p.billing_fields]}
                    if p.billing_fields else None
                ),
                "balance_note": p.balance_note,
            }
            for p in o.providers
        ],
        "keys": [
            {
                "id": k.key.id,
                "provider": k.key.provider,
                "provider_label": k.provider_label,
                "label": k.key.label,
                "hint": k.key.hint,
                "settings": dict(k.key.settings),
                "billing": {"settings": dict(k.key.billing_settings or {})} if k.key.sealed_billing else None,
                "state": k.state,
                "problem": k.problem,
                "unusable_since": k.key.unusable_at if k.key.unusable else None,
                "retry_at": k.retry_at,
                "checked_at": k.key.checked_at,
                "check_result": k.key.check_result,
                "reads_balance": k.reads_balance,
                "provider_budget": _balance(k.key.balance, k.key.balance_at),
                "provider_budget_error": k.key.balance_error,
                "spent_usd": _usd(k.spent_micros),
                "entries": k.entries,
                "created_at": k.key.created_at,
            }
            for k in o.keys
        ],
        "entries": [
            {
                "id": s.entry.id,
                "key_id": s.entry.key_id,
                "key_label": s.entry.key_label,
                "provider": s.entry.provider,
                "provider_label": s.provider_label,
                "model": s.entry.model,
                "position": s.entry.position,
                "usable": s.usable,
                "problem": s.problem,
                "monthly_cap_usd": None if s.entry.monthly_cap_micros is None else _usd(s.entry.monthly_cap_micros),
                "spent_usd": _usd(s.spent_micros),
                "left_of_cap_usd": None if s.left_of_cap_micros is None else _usd(s.left_of_cap_micros),
                "provider_budget": _balance(s.balance, s.balance_at),
                "input_price_per_mtok": s.entry.input_price_per_mtok,
                "output_price_per_mtok": s.entry.output_price_per_mtok,
            }
            for s in o.entries
        ],
        "defaults": {"monthly_cap_usd": o.settings.default_cap_usd},
        "price_presets": [
            {"provider": p.provider, "model": p.model, "input_price_per_mtok": p.input_per_mtok,
             "output_price_per_mtok": p.output_per_mtok, "source": p.source}
            for p in o.presets
        ],
        "queue": {"awaiting": o.awaiting, "flagged": o.flagged, "awaiting_reasons": o.awaiting_reasons},
        "quotas": {
            "per_user_daily": o.settings.user_daily,
            "global_daily": o.settings.global_daily,
            "calls_today": o.calls_today,
        },
    }