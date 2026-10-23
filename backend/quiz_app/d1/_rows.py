"""The one SELECT that turns a ``quiz_sets`` row into a ``QuizSetInfo``.

Shared by authoring (any status) and the catalog (published): append a WHERE
and ORDER BY to ``QUIZ_SET_SELECT``, then map rows with ``quiz_set_from_row``.
"""

from __future__ import annotations

from ..models import QuizSetInfo

QUIZ_SET_COLUMNS = """
  s.id, s.topic_id, t.name AS topic_name, t.position AS topic_position,
  s.subtopic_id, st.name AS subtopic_name, st.position AS subtopic_position,
  s.difficulty, s.style, s.seq, s.title, s.description, s.status,
  s.time_limit_minutes, s.scoring_policy,
  s.shuffle_questions, s.shuffle_options, s.reveal_answers, s.max_attempts,
  (SELECT COUNT(*) FROM questions q WHERE q.set_id = s.id) AS question_count"""

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
    )
