"""Pure grader: answer keys + selections + a scoring policy -> GradeResult."""

from __future__ import annotations

from .models import GradeResult, QuestionKey, QuestionResult
from .scoring import ScoringPolicy


def grade(
    keys: list[QuestionKey],
    selections: dict[int, frozenset[int]],
    policy: ScoringPolicy,
) -> GradeResult:
    results: list[QuestionResult] = []
    for key in keys:
        selected = selections.get(key.question_id, frozenset())
        awarded = policy.award(key.points, key.correct, selected)
        results.append(QuestionResult(key.question_id, awarded, selected == key.correct))
    return GradeResult(
        score=sum(r.awarded_points for r in results),
        max_score=sum(policy.max_award(k.points, k.correct) for k in keys),
        results=tuple(results),
    )
