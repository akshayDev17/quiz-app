"""Row mappings shared across the D1 adapters.

``QUIZ_SET_SELECT`` is the one SELECT that turns a ``quiz_sets`` row into a
``QuizSetInfo``, shared by authoring (any status) and the catalog (published):
append a WHERE and ORDER BY, then map rows with ``quiz_set_from_row``.
``review_questions`` folds question-and-option rows, from the live set or from an
attempt's paper, into ``ReviewQuestion``s.
"""

from __future__ import annotations

import json

from ..models import QuizSetInfo, ReviewOption, ReviewQuestion


def key_points_to_json(points) -> str | None:
    """A question's key points as stored: a JSON array, or ``NULL`` when there are none."""
    return json.dumps(list(points)) if points else None


def key_points_from_json(raw) -> tuple[str, ...]:
    """The stored key points; anything that is not a JSON array of strings reads as none."""
    if not raw:
        return ()
    try:
        value = json.loads(str(raw))
    except ValueError:
        return ()
    if not isinstance(value, list):
        return ()
    return tuple(p for p in value if isinstance(p, str) and p.strip())

QUIZ_SET_COLUMNS = """
  s.id, s.topic_id, t.name AS topic_name, t.position AS topic_position,
  s.subtopic_id, st.name AS subtopic_name, st.position AS subtopic_position,
  s.difficulty, s.style, s.seq, s.title, s.description, s.status,
  s.time_limit_minutes, s.scoring_policy,
  s.shuffle_questions, s.shuffle_options, s.reveal_answers, s.max_attempts, s.visibility,
  (SELECT COUNT(*) FROM questions q WHERE q.set_id = s.id) AS question_count,
  (SELECT COUNT(*) FROM questions q WHERE q.set_id = s.id AND q.kind = 'subjective') AS subjective_count"""

QUIZ_SET_FROM = """
  FROM quiz_sets s
  JOIN topics t ON t.id = s.topic_id
  LEFT JOIN subtopics st ON st.id = s.subtopic_id"""

QUIZ_SET_SELECT = f"SELECT {QUIZ_SET_COLUMNS} {QUIZ_SET_FROM}"


def quiz_set_from_row(row: dict) -> QuizSetInfo:
    return QuizSetInfo(
        id=row["id"],
        topic_id=row["topic_id"],
        topic_name=row["topic_name"],
        topic_position=row["topic_position"],
        subtopic_id=row["subtopic_id"],
        subtopic_name=row["subtopic_name"],
        subtopic_position=row["subtopic_position"],
        difficulty=row["difficulty"],
        style=row["style"],
        seq=row["seq"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        time_limit_minutes=row["time_limit_minutes"],
        scoring_policy=row["scoring_policy"],
        shuffle_questions=bool(row["shuffle_questions"]),
        shuffle_options=bool(row["shuffle_options"]),
        reveal_answers=bool(row["reveal_answers"]),
        max_attempts=row["max_attempts"],
        question_count=row["question_count"],
        subjective_count=row["subjective_count"],
        visibility=row["visibility"],
    )


def review_questions(rows: list[dict]) -> list[ReviewQuestion]:
    """Rows of a question LEFT JOIN its options, in order, folded into questions.

    Each row carries ``question_id, prompt, explanation, points, kind, model_answer,
    key_points`` and the option's ``option_id, body, is_correct``, all ``NULL`` for a
    question that has no options."""
    heads: dict[int, dict] = {}
    options: dict[int, list[ReviewOption]] = {}
    for row in rows:
        qid = row["question_id"]
        heads.setdefault(qid, row)
        options.setdefault(qid, [])
        if row["option_id"] is not None:
            options[qid].append(ReviewOption(row["option_id"], row["body"], bool(row["is_correct"])))
    return [
        ReviewQuestion(
            qid, head["prompt"], head["explanation"], head["points"], tuple(options[qid]),
            kind=head["kind"], model_answer=head["model_answer"],
            key_points=key_points_from_json(head["key_points"]),
        )
        for qid, head in heads.items()
    ]
