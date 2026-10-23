"""Wire shapes: one function per type in the wire contract (snake_case keys, epoch-ms times).

Solver-facing serializers read only from solver-facing models, so nothing here can leak
an answer while an attempt is open. ``results`` is the one place answers are exposed, and
it is reachable only for a finished attempt.
"""

from __future__ import annotations

from .models import Attempt, QuestionResult, QuizSetInfo, User
from .services.attempts import AttemptSession, ResultsView
from .validation import QuestionImport


def me(user: User) -> dict:
    return {"email": user.email, "display_name": user.display_name, "role": user.role}


def _card(info: QuizSetInfo, last: Attempt | None, open_attempt: Attempt | None) -> dict:
    return {
        "id": info.id,
        "name": info.name,
        "short_name": info.short_name,
        "difficulty": info.difficulty,
        "style": info.style,
        "time_limit_minutes": info.time_limit_minutes,
        "question_count": info.question_count,
        "last": None if last is None else {
            "attempt_id": last.id,
            "status": last.status,
            "score": last.score,
            "max_score": last.max_score,
        },
        "open_attempt": None if open_attempt is None else {
            "attempt_id": open_attempt.id,
            "deadline_at": open_attempt.deadline_at,
        },
    }


def topics(sets: list[QuizSetInfo], last: dict[int, Attempt], open_: dict[int, Attempt]) -> dict:
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
                    "sets": [_card(i, last.get(i.id), open_.get(i.id)) for i in g],
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
        "max_attempts": info.max_attempts,
        "attempts_used": attempts_used,
        "open_attempt_id": open_attempt_id,
    }


def attempt_session(session: AttemptSession) -> dict:
    attempt, info = session.attempt, session.set
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
        "set": {"name": info.name, "topic": info.topic_name, "subtopic": info.subtopic_name},
        "questions": [
            {
                "id": q.id,
                "prompt": q.prompt,
                "options": [{"id": o.id, "body": o.body} for o in q.options],
            }
            for q in session.questions
        ],
        "selections": {str(qid): sorted(ids) for qid, ids in session.selections.items()},
    }


def results(view: ResultsView) -> dict:
    attempt, info = view.attempt, view.set
    reveal = info.reveal_answers
    questions = []
    for q in view.questions:
        # Defensive: a missing result row reads as unanswered rather than failing the page.
        graded = view.results.get(q.id) or QuestionResult(q.id, 0, False)
        picked = view.selections.get(q.id, frozenset())
        questions.append({
            "id": q.id,
            "prompt": q.prompt,
            "points": q.points,
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
        },
        "set": {
            "id": info.id,
            "name": info.name,
            "topic": info.topic_name,
            "scoring_policy": info.scoring_policy,
            "reveal_answers": reveal,
        },
        "questions": questions,
    }


def history(rows: list[tuple[Attempt, QuizSetInfo]]) -> dict:
    return {
        "attempts": [
            {
                "id": a.id,
                "set_id": a.set_id,
                "name": info.name,
                "topic": info.topic_name,
                "status": a.status,
                "started_at": a.started_at,
                "finished_at": a.finished_at,
                "score": None if a.is_open else a.score,
                "max_score": None if a.is_open else a.max_score,
            }
            for a, info in rows
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
        "questions": [
            {
                "prompt": q.prompt,
                "explanation": q.explanation,
                "points": q.points,
                "options": [{"body": body, "correct": correct} for body, correct in q.options],
            }
            for q in questions
        ],
    }
